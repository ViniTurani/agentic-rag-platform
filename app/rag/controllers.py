from typing import List

from fastapi import HTTPException, UploadFile
from loguru import logger

from app.core.connectors.milvus import MilvusSearch
from app.core.pdf_uploader.embedder import AsyncEmbedder
from app.core.pdf_uploader.pdf_ingestion import ingest
from app.rag.models import ChunkDAO, FileDAO
from app.rag.schemas import IndexingResult, SearchResult, UploadResponse


async def delete_file_and_chunks(file_id: str) -> dict[str, int]:
	"""
	Remove do Mongo (Beanie) o File e todos os seus Chunks.
	Retorna o total deletado: {"file_deleted": 0|1, "chunks_deleted": N}.
	"""
	try:
		# apaga chunks
		chunk_query = ChunkDAO.find(ChunkDAO.file_id == file_id)
		del_chunks_res = await chunk_query.delete()
		chunks_deleted = getattr(del_chunks_res, "deleted_count", None)
		if chunks_deleted is None:
			# fallback caso o driver/versão não retorne contagem
			try:
				chunks_deleted = 0
			except Exception:
				chunks_deleted = 0

		file_deleted = 0
		file_doc = await FileDAO.find_one(FileDAO.id == file_id)
		if file_doc:
			del_file_res = await file_doc.delete()

			file_deleted = getattr(del_file_res, "deleted_count", None) or 1
		else:
			logger.warning(f"No file record found for file_id={file_id}")

		logger.info(
			f"Cleanup done for file_id={file_id} | "
			f"chunks_deleted={chunks_deleted} file_deleted={file_deleted}"
		)
		return {
			"chunks_deleted": int(chunks_deleted or 0),
			"file_deleted": int(file_deleted or 0),
		}
	except Exception:
		logger.exception(f"Error deleting file and chunks for file_id={file_id}")
		return {"chunks_deleted": 0, "file_deleted": 0}


async def upload_pdf_documents(files: list[UploadFile]):
	duplicate_files = 0
	total_chunks = 0
	failed_files: list[str] = []
	failed_chunks = []

	for file in files:
		fname = getattr(file, "filename", None)
		if not fname or not fname.lower().endswith(".pdf"):
			raise HTTPException(
				status_code=400, detail=f"File {fname} is not a PDF document."
			)

		logger.debug(f"Processing file: {fname}")

		res: IndexingResult | None = None
		try:
			res = await ingest(file)
		except Exception:
			logger.exception(f"Error during ingestion for file {fname}")
			failed_files.append(fname or "<unknown>")
			continue

		if not res:
			logger.error(f"Ingestion returned no result for file {fname}")
			failed_files.append(fname or "<unknown>")
			continue

		if res.total_chunks == 0:
			duplicate_files += 1
		else:
			total_chunks += res.total_chunks
			failed_chunks.extend(res.errors)

			# se todos chunks falharam no Milvus, limpamos Mongo para este arquivo
			if res.total_chunks == len(res.errors):
				logger.warning(
					"All chunks failed to be indexed for this file; "
					"removing file and chunks from Mongo."
				)
				file_id = res.inserted_file_id
				if not file_id:
					logger.error("No file_id found to delete the file and chunks.")
				else:
					await delete_file_and_chunks(file_id)

				failed_files.append(fname or "<unknown>")

	msg = f"Documents indexed successfully ({duplicate_files} duplicates found)."

	if not files:
		return UploadResponse(
			message="No files were provided.",
			documents_indexed=0,
			total_chunks=0,
			failed_chunks=[],
			failed_files=[],
		)

	docs_indexed = len(files) - duplicate_files - len(failed_files)
	if docs_indexed < 0:
		docs_indexed = 0

	if docs_indexed == 0 and (duplicate_files or failed_files):
		if duplicate_files > 0:
			msg = "No documents indexed. All files were duplicates."
		else:
			msg = "No documents indexed. All files failed to process."

	return UploadResponse(
		message=msg,
		documents_indexed=docs_indexed,
		total_chunks=total_chunks,
		failed_chunks=failed_chunks,
		failed_files=failed_files,
	)


async def hybrid_search(
	query: str,
	sparse_weight: float = 0.5,
	dense_weight: float = 0.5,
	top_k: int = 5,
) -> List[SearchResult]:
	embedder = AsyncEmbedder()
	milvus = MilvusSearch()

	# embed the query
	[qvec] = await embedder.encode([query])

	raw = milvus.search(
		query=query,
		dense_embedding=qvec,
		expr="",
		dense_weight=dense_weight,
		sparse_weight=sparse_weight,
		limit=top_k,
	)

	hits: list = []
	if isinstance(raw, dict):
		maybe_hits = raw.get("data")
		if isinstance(maybe_hits, list):
			hits = maybe_hits
	elif isinstance(raw, list):
		hits = raw

	results: list[SearchResult] = []
	for h in hits[:top_k]:
		if not isinstance(h, dict):
			continue
		text = h.get("text") or ""
		results.append(
			SearchResult(
				text=str(text),
				source=h.get("source"),
				file_id=h.get("file_id"),
				page=h.get("page"),
				chunk_index=h.get("chunk_index"),
				filename=h.get("filename"),
				score=h.get("distance"),
			)
		)

	return results
