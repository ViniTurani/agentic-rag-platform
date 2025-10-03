import hashlib

from beanie import PydanticObjectId
from fastapi import HTTPException, UploadFile
from loguru import logger
from pymupdf import open as pdf_open

from app.core.connectors.milvus import MilvusInsert
from app.core.metrics import INGEST_CHUNKS, INGEST_DUPLICATES, INGEST_FILES, observe
from app.rag.models import ChunkDAO, FileDAO
from app.rag.schemas import Chunk, IndexingResult

from .chunkfier import chunkfy_pages
from .embedder import AsyncEmbedder
from .parser import markdown_parse


def _sha256(data: bytes) -> str:
	return hashlib.sha256(data).hexdigest()


async def create_and_insert_chunks(
	chunks: list[Chunk], file_id: PydanticObjectId
) -> list[str]:
	"""
	Converts Chunk schemas to Beanie documents (ChunkDAO) and inserts them in bulk.
	Returns the list of inserted IDs (as strings).
	"""
	if not chunks:
		return []

	try:
		chunk_docs = []
		for chunk in chunks:
			data = chunk.model_dump(by_alias=True)
			single_doc = ChunkDAO(**data, file_id=file_id)
			chunk_docs.append(single_doc)

		result = await ChunkDAO.insert_many(chunk_docs)

		inserted_ids = [str(id_) for id_ in result.inserted_ids]
		logger.debug(f"Inserted {len(inserted_ids)} chunks into MongoDB")

		return inserted_ids
	except Exception as e:
		logger.exception(f"Error inserting chunks into MongoDB: {str(e)}")
		return []


async def create_and_save_file_record(
	file_hash: str,
	filename: str | None,
	title: str | None,
	content: str,
	total_pages: int,
	size_bytes: int,
	mime: str,
) -> PydanticObjectId:
	"""
	Creates and inserts the file record (FileDAO) with automatic timestamps.
	Returns the id of the inserted document (PydanticObjectId).
	"""

	file_id = PydanticObjectId()
	file_doc = FileDAO(
		id=file_id,
		file_hash=file_hash,
		filename=filename,
		title=title,
		content=content,
		total_pages=total_pages,
		size_bytes=size_bytes,
		mime=mime,
	)
	await file_doc.insert()
	logger.debug(f"Saved file record on MongoDB with _id={file_doc.id}")
	return file_id


async def ingest(full_pdf: UploadFile) -> IndexingResult:
	"""
	Complete ingestion of a PDF:
	- Deduplicate by hash.
	- Parse into markdown pages.
	- Save the file record in MongoDB (Beanie).
	- Chunkfy and save chunks in MongoDB (Beanie).
	- Embed and insert into Milvus.
	Returns an IndexingResult with details of the operation.
	"""
	INGEST_FILES.inc()

	# 1) extract bytes check for duplicates
	pdf_bytes = await full_pdf.read()
	if not pdf_bytes:
		raise HTTPException(status_code=400, detail="Empty file")

	file_hash = _sha256(pdf_bytes)

	existing = await FileDAO.find_one(FileDAO.file_hash == file_hash)
	if existing:
		INGEST_DUPLICATES.inc()
		logger.debug(f"Duplicate file detected (hash={file_hash}); skipping embedding.")
		return IndexingResult(
			total_chunks=0,
			errors=[],
			message="Duplicate file; skipping embedding.",
		)

	# 1.1) parse PDF to markdown
	with observe("parse"):
		doc = pdf_open(stream=pdf_bytes, filetype="pdf")
		try:
			pages = markdown_parse(doc)
		finally:
			try:
				doc.close()
			except Exception:
				logger.debug("Failed to close PDF document handle (ignored).")

		if not pages:
			raise HTTPException(
				status_code=400, detail="No text found in the PDF document."
			)

	file_id = await create_and_save_file_record(
		file_hash=file_hash,
		filename=full_pdf.filename,
		title=(doc.metadata or {}).get("title") if hasattr(doc, "metadata") else None,
		content=" ".join(p.get("text", "") for p in pages),
		total_pages=len(pages),
		size_bytes=len(pdf_bytes),
		mime=full_pdf.content_type or "application/pdf",
	)

	logger.debug(
		f"Extracted {len(pages)} pages from PDF, "
		f"and file saved on MongoDB (file_id={file_id})"
	)

	with observe("chunkfy"):
		chunks: list[Chunk] = chunkfy_pages(
			pages,
			file_id=str(file_id),
			filename=full_pdf.filename,
			title=(doc.metadata or {}).get("title")
			if hasattr(doc, "metadata")
			else None,
			max_chars=1200,
			overlap=150,
		)

	logger.debug(f"Chunked into {len(chunks)} text chunks")

	inserted_chunks = await create_and_insert_chunks(chunks, file_id=file_id)
	if not inserted_chunks:
		raise HTTPException(
			status_code=400, detail="Failed to insert chunks into MongoDB."
		)
	INGEST_CHUNKS.inc(len(chunks))

	# 4) embed + insert on Milvus
	embedder = AsyncEmbedder()
	milvus_client = MilvusInsert()

	return await milvus_client.upload_chunks(
		chunks,
		embedder=embedder,
		file_id=str(file_id),
		chunk_ids=inserted_chunks,
	)
