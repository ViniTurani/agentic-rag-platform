import asyncio
from typing import List

import httpx
from loguru import logger

from app.core.metrics import (
	MILVUS_INSERT_BATCHES,
	MILVUS_INSERT_ERRORS,
	SEARCH_ERRORS,
	SEARCH_REQUESTS,
	observe,
)
from app.core.pdf_uploader.embedder import AsyncEmbedder
from app.rag.schemas import Chunk, EmbeddedChunk, FailedChunk, IndexingResult
from app.settings import Settings


class MilvusInsert:
	def __init__(self):
		sets = Settings.get()
		self.collection_name = sets.MILVUS_COLLECTION
		self.cluster_endpoint = sets.MILVUS_URL.rstrip("/")
		self.token = sets.MILVUS_SECRET
		self.BATCH_SIZE = 64
		self.VECTOR_FIELD = "vector"

	async def insert(self, data: List[EmbeddedChunk]):
		url = f"{self.cluster_endpoint}/v2/vectordb/entities/insert"
		headers = {
			"Content-Type": "application/json",
		}
		if self.token:
			headers["Authorization"] = f"Bearer {self.token}"

		payload = {
			"collectionName": self.collection_name,
			"data": [d.model_dump() for d in data],
		}
		async with httpx.AsyncClient(timeout=60) as client:
			resp = await client.post(url, json=payload, headers=headers)
			resp.raise_for_status()
			resp_json = resp.json()
			if resp_json.get("code") != 0:
				raise httpx.HTTPStatusError(
					f"Milvus insert error: {resp_json}",
					request=resp.request,
					response=resp,
				)
			return resp.json()
		return {}

	async def upload_chunks(
		self,
		chunks: List[Chunk],
		embedder: "AsyncEmbedder",
		file_id: str,
		chunk_ids: List[str],
	) -> IndexingResult:
		"""
		Insert chunk embeddings into Milvus and return an IndexingResult.
		'chunks' must contain: id, file_id, page, chunk_index, source, text
		"""
		n = len(chunks)
		logger.debug(
			f"Inserting {n} chunks into Milvus collection '{self.collection_name}'"
		)

		# launch batch tasks; each returns List[FailedChunk]
		tasks = []
		for start in range(0, n, self.BATCH_SIZE):
			batch = chunks[start : start + self.BATCH_SIZE]
			tasks.append(self._process_batch(batch, embedder))

		batch_results = await asyncio.gather(*tasks)
		# flatten errors
		errors: List[FailedChunk] = [err for errs in batch_results for err in errs]
		return IndexingResult(
			total_chunks=n,
			errors=errors,
			message="Documents uploaded successfully",
			inserted_file_id=str(file_id),
			inserted_chunk_ids=[str(cid) for cid in chunk_ids],
		)

	async def _process_batch(
		self, batch: List[Chunk], embedder: "AsyncEmbedder"
	) -> List[FailedChunk]:
		"""Embed + insert one batch; collect failures per chunk."""
		# 1) Embed
		try:
			texts = [c.text for c in batch]
			vectors = await embedder.encode(texts)
		except Exception as e:
			msg = _short_err("embed", e)
			return [
				FailedChunk(
					chunk=c,
					error=msg,
					filename=c.filename,
				)
				for c in batch
			]

		# if model returned fewer vectors than inputs, mark missing ones
		errors: List[FailedChunk] = []
		if len(vectors) != len(batch):
			msg = f"embed: length mismatch (got {len(vectors)}, expected {len(batch)})"
			# mark all as failed, safest fallback
			return [
				FailedChunk(
					chunk=c,
					error=msg,
					filename=c.filename,
				)
				for c in batch
			]

		# 2) Build entities
		entities: List[EmbeddedChunk] = []
		for c, v in zip(batch, vectors):
			try:
				entities.append(
					EmbeddedChunk(
						**c.model_dump(by_alias=True, exclude={"title"}),
						title=c.title or "N/A",
						vector=(
							v.tolist()  # type: ignore
							if hasattr(v, "tolist")
							else [float(x) for x in v]  # type: ignore
						),
					)
				)
			except Exception as e:
				errors.append(
					FailedChunk(
						chunk=c,
						error=_short_err("prepare", e),
						filename=c.filename,
					)
				)

		# if all failed to prepare, stop here
		if not entities:
			return errors

		# 3) Insert
		try:
			MILVUS_INSERT_BATCHES.inc()
			with observe("milvus_insert"):
				await self.insert(entities)
		except httpx.HTTPStatusError as e:
			MILVUS_INSERT_ERRORS.inc()

			status = e.response.status_code if e.response else "?"
			body = ""
			try:
				body = e.response.text[:500] if e.response is not None else ""
			except Exception:
				body = str(e)
			msg = f"insert HTTP {status}: {body}"
			# mark entire batch as failed (only those we attempted to insert)
			errors.extend(
				FailedChunk(
					chunk=ent,
					error=msg,
					filename=ent.filename,
				)
				for ent in entities
			)
			logger.error(f"Milvus insert error: {msg}")
		except Exception as e:
			MILVUS_INSERT_ERRORS.inc()
			msg = _short_err("insert", e)
			errors.extend(
				FailedChunk(
					chunk=ent,
					error=msg,
					filename=ent.filename,
				)
				for ent in entities
			)
			logger.error(f"Milvus insert error: {msg}")

		return errors


def _short_err(stage: str, e: Exception, limit: int = 300) -> str:
	s = f"{stage}: {type(e).__name__}: {str(e)}"
	return (s[: limit - 3] + "...") if len(s) > limit else s


class MilvusSearch:
	def __init__(self):
		sets = Settings.get()
		self.cluster_endpoint = sets.MILVUS_URL.rstrip("/")
		self.token = sets.MILVUS_SECRET
		self.collection_name = "doc_chunks"

	def search(
		self,
		query: str,
		dense_embedding: list[float],
		expr: str,
		dense_weight: float,
		sparse_weight: float,
		limit: int = 3,
	) -> dict:
		SEARCH_REQUESTS.inc()
		url = f"{self.cluster_endpoint}/v2/vectordb/entities/advanced_search"
		headers = {
			"Content-Type": "application/json",
		}
		if self.token:
			headers["Authorization"] = f"Bearer {self.token}"

		payload = {
			"collectionName": self.collection_name,
			"search": [
				{
					"data": [dense_embedding],  # type: ignore
					"annsField": "vector",
					"params": {"params": {"nprobe": 10}},
					"limit": limit,
					"filter": expr,
				},
				{
					"data": [query],
					"annsField": "sparse_vector",
					"params": {},
					"limit": limit,
					"filter": expr,
				},
			],
			"rerank": {
				"strategy": "weighted",
				"params": {"weights": [dense_weight, sparse_weight]},
			},
			"limit": limit,
			"outputFields": [
				"text",
				"source",
				"filename",
				"file_id",
				"page",
				"chunk_index",
			],
		}
		with observe("milvus_search"):
			try:
				with httpx.Client(timeout=60) as client:
					response = client.post(url, json=payload, headers=headers)
					response.raise_for_status()
			except Exception as e:
				SEARCH_ERRORS.inc()
				msg = _short_err("milvus_search", e)
				logger.error(f"Milvus search error: {msg}")
				raise

		return response.json()
