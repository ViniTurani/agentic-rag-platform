from typing import Any, Dict, Optional

import httpx
from loguru import logger

from .settings import Settings

setts = Settings.get()
DEFAULT_DB = "default"
DIMENSIONS = 1536  # default for the embedding model used on the application


def _auth_headers(token: Optional[str]) -> Dict[str, str]:
	headers = {"Content-Type": "application/json"}
	if token and str(token).strip():
		headers["Authorization"] = f"Bearer {token}"
	return headers


async def _post(
	base_url: str,
	path: str,
	token: Optional[str],
	payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
	url = f"{base_url.rstrip('/')}{path}"
	async with httpx.AsyncClient(timeout=60) as client:
		resp = await client.post(
			url, headers=_auth_headers(token), json=(payload or {})
		)

	# Try to parse JSON regardless of HTTP status to capture Milvus message
	try:
		body = resp.json()
	except ValueError:
		resp.raise_for_status()
		return {}

	if resp.status_code >= 400:
		# Include Milvus JSON body in error for easier debugging
		raise httpx.HTTPStatusError(
			f"{resp.status_code} {resp.reason_phrase}: {body}",
			request=resp.request,
			response=resp,
		)

	# Milvus logical error code handling (idempotent-friendly)
	code = body.get("code", 0)
	if code and code != 0:
		msg = str(body.get("message", ""))
		# treat typical idempotent cases as success
		idempotent_markers = (
			"already exist",
			"duplicated",
			"has been created",
		)
		if any(m in msg.lower() for m in idempotent_markers):
			return body
		raise RuntimeError(f"Milvus error code={code}: {msg}")

	return body


async def list_collections(
	base_url: str, token: Optional[str], db_name: str = DEFAULT_DB
) -> Dict[str, Any]:
	return await _post(
		base_url, "/v2/vectordb/collections/list", token, {"dbName": db_name}
	)


async def collection_exists(
	base_url: str, token: Optional[str], collection_name: str, db_name: str = DEFAULT_DB
) -> bool:
	data = (await list_collections(base_url, token, db_name)).get("data", {})
	if type(data) is not list:
		return False
	names = [item.get("name") for item in data if "name" in item]
	return collection_name in names


async def create_doc_chunks_collection(
	base_url: str, token: Optional[str], collection_name: str, dim: int
) -> Dict[str, Any]:
	"""Create the `doc_chunks` collection (schema + functions) as in your Docker Compose

	Schema:
	- pk (Int64, primary, autoID)
	- chunk_id, file_id, filename, title, source (VarChar)
	- page_idx, chunk_idx (Int64)
	- text (VarChar, analyzer enabled with multi_analyzer_params)
	- sparse_vector (SparseFloatVector)
	- vector (FloatVector, dim=dim)
	- functions: BM25(text -> sparse_vector)
	"""
	payload: Dict[str, Any] = {
		"collectionName": collection_name,
		"schema": {
			"enableDynamicField": True,
			"autoID": True,
			"fields": [
				{
					"fieldName": "id",
					"dataType": "Int64",
					"isPrimary": True,
				},
				{
					"fieldName": "chunk_id",
					"dataType": "VarChar",
					"elementTypeParams": {"max_length": 64},
				},
				{
					"fieldName": "file_id",
					"dataType": "VarChar",
					"elementTypeParams": {"max_length": 64},
				},
				{
					"fieldName": "filename",
					"dataType": "VarChar",
					"elementTypeParams": {"max_length": 256},
				},
				{
					"fieldName": "title",
					"dataType": "VarChar",
					"elementTypeParams": {"max_length": 256},
				},
				{"fieldName": "page_idx", "dataType": "Int64"},
				{"fieldName": "chunk_idx", "dataType": "Int64"},
				{
					"fieldName": "source",
					"dataType": "VarChar",
					"elementTypeParams": {"max_length": 256},
				},
				{
					"fieldName": "text",
					"dataType": "VarChar",
					"elementTypeParams": {
						"max_length": 65535,
						"enable_analyzer": True,
					},
				},
				{"fieldName": "sparse_vector", "dataType": "SparseFloatVector"},
				{
					"fieldName": "vector",
					"dataType": "FloatVector",
					"elementTypeParams": {"dim": int(dim)},
				},
			],
			"functions": [
				{
					"name": "text_to_sparse",
					"type": "BM25",
					"inputFieldNames": ["text"],
					"outputFieldNames": ["sparse_vector"],
					"params": {},
				}
			],
		},
	}
	return await _post(base_url, "/v2/vectordb/collections/create", token, payload)


essential_indexes = [
	{
		"fieldName": "vector",
		"indexName": "hnsw_vector",
		"indexType": "HNSW",
		"metricType": "COSINE",
		"params": {"M": 16, "efConstruction": 200},
	},
	{
		"fieldName": "sparse_vector",
		"indexName": "sparse_bm25",
		"indexType": "SPARSE_INVERTED_INDEX",
		"metricType": "BM25",
		"params": {},
	},
]


async def create_index(
	base_url: str,
	token: Optional[str],
	collection_name: str,
	index_spec: list[Dict[str, Any]],
) -> Dict[str, Any]:
	payload = {"collectionName": collection_name, "indexParams": index_spec}
	try:
		return await _post(base_url, "/v2/vectordb/indexes/create", token, payload)
	except Exception as e:
		msg = str(e).lower()
		if "already exist" in msg or "index exist" in msg:
			return {"code": 0, "message": "index already exists (treated as success)"}
		raise


async def load_collection(
	base_url: str, token: Optional[str], collection_name: str
) -> Dict[str, Any]:
	return await _post(
		base_url,
		"/v2/vectordb/collections/load",
		token,
		{"collectionName": collection_name},
	)


async def init_milvus() -> None:
	"""Idempotent bootstrap: ensure collection, indexes, and load are in place.

	Settings used:
	- MILVUS_URL        (default: http://milvus:19530)
	- MILVUS_SECRET     (default: none; header omitted)
	- MILVUS_COLLECTION (default: doc_chunks)
	"""
	base_url = setts.MILVUS_URL
	token: Optional[str] = setts.MILVUS_SECRET
	collection_name: str = setts.MILVUS_COLLECTION
	dim: int = DIMENSIONS  # default for the embedding model used on the application

	logger.info(
		f"Initializing Milvus at {base_url} to initialize collection {collection_name}"
	)

	# 1) create collection if not exists
	if not await collection_exists(base_url, token, collection_name):
		res = await create_doc_chunks_collection(base_url, token, collection_name, dim)
		logger.info(f"Created collection {collection_name}: {res}")
	else:
		logger.info(
			f"Collection {collection_name} already exists - skipping its creation"
		)

	# 2) create required indexes
	index_results: Dict[str, Any] = {}
	index_results = await create_index(
		base_url, token, collection_name, essential_indexes
	)
	logger.info(f"Index creation results: {index_results}")

	# 3) load collection (safe to call multiple times)
	await load_collection(base_url, token, collection_name)
	logger.info(f"Loaded collection {collection_name}")
