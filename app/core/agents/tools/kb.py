import json
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from agents import RunContextWrapper
from app.core.connectors.milvus import MilvusSearch
from app.core.pdf_uploader.embedder import AsyncEmbedder


class Arguments(BaseModel):
	query: str = Field(..., description="The search query")
	top_k: int = Field(3, description="Number of top results to return")
	sparse_weight: float = Field(
		0.5, description="Weight for sparse search results (0.0 to 1.0)"
	)
	dense_weight: float = Field(
		0.5, description="Weight for dense search results (0.0 to 1.0)"
	)


async def kb_retrieve(ctx: RunContextWrapper[Any], args: str) -> str:
	try:
		parsed = Arguments.model_validate_json(args)
		embedder = AsyncEmbedder()
		milvus = MilvusSearch()

		logger.debug(
			f"Query: {parsed.query}, top_k: {parsed.top_k},"
			f" sparse_weight: {parsed.sparse_weight}, "
			f"dense_weight: {parsed.dense_weight}"
		)

		# Embed the query
		vectors = await embedder.encode([parsed.query])

		if not vectors:
			return "[]"
		query_vec = vectors[0]

		logger.debug(f"Query vector length: {len(query_vec)}")
		logger.info("Performing hybrid search in Milvus")

		raw = milvus.search(
			query=parsed.query,
			dense_embedding=query_vec,
			expr="",
			dense_weight=parsed.dense_weight,
			sparse_weight=parsed.sparse_weight,
			limit=parsed.top_k,
		)

		# Normalize Milvus response into a list of hit dicts
		hits = []
		if isinstance(raw, dict):
			maybe_hits = raw.get("data")
			if isinstance(maybe_hits, list):
				hits = [h for h in maybe_hits if isinstance(h, dict)]
		elif isinstance(raw, list):
			hits = [h for h in raw if isinstance(h, dict)]  # type: ignore

		# Build items to return as JSON
		items = []
		for h in hits[: parsed.top_k]:
			text_val = h.get("text")
			if text_val is None:
				text_val = ""
			items.append(
				{
					"text": str(text_val),
					"source": h.get("source", "not provided"),
					"file_id": h.get("file_id", ""),
					"page": h.get("page", None),
					"chunk_index": h.get("chunk_index", None),
					"filename": h.get("filename", "not provided"),
					"score": h.get("distance", None),
				}
			)

		logger.debug(f"kb_retrieve returning {len(items)} items")

		return json.dumps(items, ensure_ascii=False)

	except Exception as e:
		logger.error(f"kb_retrieve failed: {e}")
		return "[]"
