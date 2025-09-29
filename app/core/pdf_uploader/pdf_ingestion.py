import hashlib
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from loguru import logger
from pymupdf import open as pdf_open

from app.rag.models import ChunkDAO, FileDAO
from app.rag.schemas import Chunk, IndexingResult

from app.core.connectors.milvus import MilvusInsert
from app.core.connectors.mongo import MongoHelper
from .embedder import AsyncEmbedder
from app.core.metrics import (
	INGEST_CHUNKS,
	INGEST_DUPLICATES,
	INGEST_FILES,
	observe,
)
from .chunkifier import chunkfy_pages
from .parser import markdown_parse

mongo_client = MongoHelper()


def create_and_insert_chunks(chunks: list[Chunk]) -> list[str]:
	# save chunks to MongoDB
	try:
		dict_chunks = [c.model_dump(by_alias=True) for c in chunks]
		inserted_ids = mongo_client.insert_many(dict_chunks, model=ChunkDAO)
		return inserted_ids
	except Exception as e:
		logger.error(f"Error inserting chunks into MongoDB: {e}")
		return []


def _sha256(data: bytes) -> str:
	return hashlib.sha256(data).hexdigest()


def create_and_save_file_record(
	file_id: str,
	file_hash: str,
	filename: str | None,
	title: str | None,
	content: str,
	total_pages: int,
	size_bytes: int,
	mime: str,
) -> str:
	file_record = FileDAO(
		file_id=file_id,
		file_hash=file_hash,
		filename=filename,
		title=title,
		content=content,
		total_pages=total_pages,
		size_bytes=size_bytes,
		mime=mime,
		created_at=datetime.now(),
	)
	return mongo_client.insert_one(file_record.model_dump(by_alias=True), model=FileDAO)


async def ingest(full_pdf: UploadFile) -> IndexingResult:
	INGEST_FILES.inc()

	# 1) extract and check for duplicates
	file_id = uuid4().int
	pdf_bytes = await full_pdf.read()
	file_hash = _sha256(pdf_bytes)

	# use file hash on content bytes
	existing = mongo_client.read_one(filter={"file_hash": file_hash}, model=FileDAO)
	if existing:
		INGEST_DUPLICATES.inc()
		logger.debug(f"Duplicate file detected (hash={file_hash}); skipping embedding.")
		return IndexingResult(
			total_chunks=0,
			errors=[],
			message="Duplicate file; skipping embedding.",
		)

	# 1.1) extract text as markdown pages
	with observe("parse"):
		doc = pdf_open(stream=pdf_bytes, filetype="pdf")
		pages = markdown_parse(doc)
		if not pages:
			raise ValueError("No text found in the PDF document.")

	# 2) save on mongo the whole files
	created_file = create_and_save_file_record(
		file_id=str(file_id),
		file_hash=file_hash,
		filename=full_pdf.filename,
		title=(doc.metadata or {}).get("title"),
		content=" ".join(p.get("text", "") for p in pages),
		total_pages=len(pages),
		size_bytes=full_pdf.size or 0,
		mime=full_pdf.content_type or "application/pdf",
	)
	if not created_file:
		raise HTTPException(
			status_code=400, detail="Failed to insert file into MongoDB."
		)
	logger.debug(f"Extracted {len(pages)} pages from PDF, and file saved on MongoDB")

	# 3) chunkfy the text pages
	with observe("chunkfy"):
		chunks: list[Chunk] = chunkfy_pages(
			pages,
			file_id=str(file_id),
			filename=full_pdf.filename,
			title=(doc.metadata or {}).get("title"),
			max_chars=1200,
			overlap=150,
		)

	logger.debug(f"Chunked into {len(chunks)} text chunks")
	# 3.1) save on mongo the chunks
	inserted_chunks = create_and_insert_chunks(chunks)
	if not inserted_chunks:
		raise HTTPException(
			status_code=400, detail="Failed to insert chunks into MongoDB."
		)

	INGEST_CHUNKS.inc(len(chunks))

	# 4) upsert into milvus (embeds + inserts in batches)
	embedder = AsyncEmbedder()
	milvus_client = MilvusInsert()
	upload_res = await milvus_client.upload_chunks(chunks, embedder=embedder)
	return IndexingResult(
		**upload_res.model_dump(by_alias=True, exclude=["inserted_file_id"]),
		inserted_file_id=str(file_id),
	)
