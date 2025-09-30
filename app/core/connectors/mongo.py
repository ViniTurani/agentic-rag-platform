from typing import TypeAlias

from loguru import logger
from pymongo import MongoClient

from ...rag.models import Document
from ...settings import Settings

setts = Settings.get()


T: TypeAlias = Document


class MongoHelper:
	def __init__(self):
		uri = setts.MONGO_URI
		db = setts.MONGO_DB

		self.client = MongoClient(uri)
		self.db = self.client[db]

	# inserts
	def insert_one(self, doc: dict, model: type[T]) -> str:
		coll_name = model.get_collection_name()
		coll = self.db[coll_name]

		try:
			res = coll.insert_one(doc)
			return str(res.inserted_id)
		except Exception as e:
			logger.error(f"Error inserting document into MongoDB: {e}")
			return ""

	def insert_many(self, docs: list[dict], model: type[T]) -> list[str]:
		if not docs:
			return []

		coll_name = model.get_collection_name()
		coll = self.db[coll_name]

		try:
			res = coll.insert_many(docs)
			return [str(_id) for _id in res.inserted_ids]
		except Exception as e:
			logger.error(f"Error inserting documents into MongoDB: {e}")
			return []

	# reads
	def read_one(
		self, model: type[T], filter: dict | None = None, projection: dict | None = None
	) -> dict | None:
		coll_name = model.get_collection_name()
		coll = self.db[coll_name]
		try:
			return coll.find_one(filter or {}, projection)
		except Exception as e:
			logger.error(f"Error reading document from MongoDB: {e}")
			return None

	def read_many(
		self,
		model: type[T],
		filter: dict | None = None,
		projection: dict | None = None,
		limit: int = 50,
		skip: int = 0,
		sort: list[tuple[str, int]] | None = None,  # e.g. [("created_at", -1)]
	) -> list[dict]:
		coll_name = model.get_collection_name()
		coll = self.db[coll_name]

		try:
			cur = coll.find(filter or {}, projection)
			if sort:
				cur = cur.sort(sort)
			if skip:
				cur = cur.skip(int(skip))
			if limit:
				cur = cur.limit(int(limit))
			return list(cur)
		except Exception as e:
			logger.error(f"Error reading documents from MongoDB: {e}")
			return []

	def close(self) -> None:
		self.client.close()

	def delete_one(self, model: type[T], filter: dict) -> int:
		coll_name = model.get_collection_name()
		coll = self.db[coll_name]

		try:
			res = coll.delete_one(filter)
			return res.deleted_count
		except Exception as e:
			logger.error(f"Error deleting document from MongoDB: {e}")
			return 0

	def delete_many(self, filter: dict, model: type[T]) -> int:
		coll_name = model.get_collection_name()
		coll = self.db[coll_name]

		try:
			res = coll.delete_many(filter)
			return res.deleted_count
		except Exception as e:
			logger.error(f"Error deleting documents from MongoDB: {e}")
			return 0
