from typing import List

from fastapi import UploadFile
from loguru import logger

from app.core.connectors.milvus import MilvusSearch
from app.core.pdf_uploader.embedder import AsyncEmbedder
from app.core.pdf_uploader.pdf_ingestion import ingest
from app.core.utils import delete_file_and_chunks
from app.rag.schemas import SearchResult

from .schemas import (
	IndexingResult,
	UploadResponse,
)


async def upload_pdf_documents(files: list[UploadFile]):
	res: IndexingResult | None = None
	duplicate_files = 0
	total_chunks = 0
	failed_files = []
	failed_chunks = []
	for file in files:
		logger.debug(f"Processing file: {file.filename}")
		res = await ingest(file)

		if not res:
			logger.error(
				f"Error during ingestion for file {file.filename} - no result returned."
			)
			failed_files.append(file.filename)
			continue

		if res.total_chunks == 0:
			duplicate_files += 1

		total_chunks += res.total_chunks
		failed_chunks.extend(res.errors)
	msg = f"Documents indexed successfully ({duplicate_files} duplicates found)."

	if not res:
		msg = "No files were processed - something went wrong on the file uploading."
		return UploadResponse(
			message=msg,
			documents_indexed=0,
			total_chunks=0,
			failed_chunks=[],
			failed_files=[f.filename if f.filename else "<unknown>" for f in files],
		)

	if res.total_chunks != 0 and res.total_chunks == len(
		res.errors
	):  # all chunks failed
		# remove everything from mongo that was just added
		logger.warning(
			"Trying to remove everything that was just"
			" added due to failures on all milvus insertion for the chunks."
		)
		file_id = res.inserted_file_id
		if not file_id:
			logger.error("No file_id found to delete the file and chunks.")
		else:
			delete_file_and_chunks(file_id)

		msg = (
			"All chunks failed to be indexed; "
			"the file and its chunks were removed from mongo."
		)

	return UploadResponse(
		message=msg,
		documents_indexed=len(files) - duplicate_files - len(failed_files),
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
	# Normalize Milvus response: expected shape includes top-level 'data' list already
	hits = []

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
