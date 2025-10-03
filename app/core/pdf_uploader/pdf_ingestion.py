import hashlib
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from loguru import logger
from pymupdf import open as pdf_open

from app.core.connectors.milvus import MilvusInsert
from app.core.metrics import INGEST_CHUNKS, INGEST_DUPLICATES, INGEST_FILES, observe
from app.rag.models import ChunkDAO, FileDAO
from app.rag.schemas import Chunk, IndexingResult

from .chunkifier import chunkfy_pages
from .embedder import AsyncEmbedder
from .parser import markdown_parse


def _sha256(data: bytes) -> str:
	return hashlib.sha256(data).hexdigest()


async def create_and_insert_chunks(chunks: list[Chunk]) -> list[str]:
	"""
	Converte os schemas Chunk em documentos Beanie (ChunkDAO) e insere em lote.
	Retorna a lista de IDs inseridos (string).
	"""
	if not chunks:
		return []

	try:
		chunk_docs = [ChunkDAO(**c.model_dump(by_alias=True)) for c in chunks]

		result = await ChunkDAO.insert_many(chunk_docs)

		for i, doc in enumerate(chunk_docs):
			if i < len(result.inserted_ids):
				doc.id = result.inserted_ids[i]

		inserted_ids = [str(doc.id) for doc in chunk_docs if getattr(doc, "id", None)]
		logger.debug(f"Inserted {len(inserted_ids)} chunks into MongoDB")

		if len(inserted_ids) == 0 and len(chunks) > 0:
			logger.error(
				f"No IDs were created despite having {len(chunks)} chunks to insert"
			)
			# Tentativa de inserção individual para debug
			for i, chunk in enumerate(chunks[:3]):
				try:
					single_doc = ChunkDAO(**chunk.model_dump(by_alias=True))
					await single_doc.insert()
					logger.debug(
						f"Individual insert test #{i} succeeded ID: {single_doc.id}"
					)
				except Exception as e:
					logger.error(f"Individual insert test #{i} failed: {str(e)}")

		return inserted_ids
	except Exception as e:
		logger.exception(f"Error inserting chunks into MongoDB: {str(e)}")
		return []


async def create_and_save_file_record(
	file_id: str,
	file_hash: str,
	filename: str | None,
	title: str | None,
	content: str,
	total_pages: int,
	size_bytes: int,
	mime: str,
) -> str:
	"""
	Cria e insere o registro do arquivo (FileDAO) com timestamps automaticos.
	Retorna o id do documento inserido (string).
	"""
	try:
		file_doc = FileDAO(
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
		return str(file_doc.id)
	except Exception:
		logger.exception("Error inserting file into MongoDB")
		return ""


async def ingest(full_pdf: UploadFile) -> IndexingResult:
	"""
	Ingestao completa de um PDF:
	- Dedup por hash.
	- Parse para paginas markdown.
	- Salva registro do arquivo no MongoDB (Beanie).
	- Chunkify e salva chunks no MongoDB (Beanie).
	- Embedding + insert no Milvus.
	Retorna IndexingResult com detalhes da operacao.
	"""
	INGEST_FILES.inc()

	# 1) extract bytes e checagem de duplicidade
	file_id = uuid4().hex  # curto e 64-safe
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

	# 1.1) parse PDF em paginas markdown
	with observe("parse"):
		doc = pdf_open(stream=pdf_bytes, filetype="pdf")
		try:
			pages = markdown_parse(doc)
		finally:
			# garantir liberacao do recurso
			try:
				doc.close()
			except Exception:
				logger.debug("Failed to close PDF document handle (ignored).")

		if not pages:
			raise HTTPException(
				status_code=400, detail="No text found in the PDF document."
			)

	# 2) salva arquivo no Mongo
	created_file_id = await create_and_save_file_record(
		file_id=file_id,
		file_hash=file_hash,
		filename=full_pdf.filename,
		title=(doc.metadata or {}).get("title") if hasattr(doc, "metadata") else None,
		content=" ".join(p.get("text", "") for p in pages),
		total_pages=len(pages),
		size_bytes=len(pdf_bytes),
		mime=full_pdf.content_type or "application/pdf",
	)
	if not created_file_id:
		raise HTTPException(
			status_code=400, detail="Failed to insert file into MongoDB."
		)

	logger.debug(
		f"Extracted {len(pages)} pages from PDF, "
		f"and file saved on MongoDB (file_id={file_id})"
	)

	# 3) chunkfy paginas
	with observe("chunkfy"):
		chunks: list[Chunk] = chunkfy_pages(
			pages,
			file_id=file_id,
			filename=full_pdf.filename,
			title=(doc.metadata or {}).get("title")
			if hasattr(doc, "metadata")
			else None,
			max_chars=1200,
			overlap=150,
		)

	logger.debug(f"Chunked into {len(chunks)} text chunks")

	# 3.1) salva chunks no Mongo
	inserted_chunks = await create_and_insert_chunks(chunks)
	if not inserted_chunks:
		raise HTTPException(
			status_code=400, detail="Failed to insert chunks into MongoDB."
		)
	INGEST_CHUNKS.inc(len(chunks))

	# 4) embed + insert no Milvus
	embedder = AsyncEmbedder()
	milvus_client = MilvusInsert()
	upload_res = await milvus_client.upload_chunks(chunks, embedder=embedder)

	return IndexingResult(
		**upload_res.model_dump(by_alias=True, exclude={"inserted_file_id"}),
		inserted_file_id=file_id,
	)
