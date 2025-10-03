import pymongo
from beanie import Document, PydanticObjectId

from app.core.db.timestamps import TimestampingMixin

from .schemas import Chunk, File


class FileDAO(File, TimestampingMixin, Document):
	class Settings:
		name = "files"
		indexes = [
			pymongo.IndexModel([("file_hash", pymongo.ASCENDING)]),
			pymongo.IndexModel([("created_at", pymongo.DESCENDING)]),
		]


class ChunkDAO(Chunk, TimestampingMixin, Document):
	file_id: PydanticObjectId

	class Settings:
		name = "chunks"
		indexes = [
			pymongo.IndexModel([("file_id", pymongo.ASCENDING)]),
			pymongo.IndexModel([("created_at", pymongo.DESCENDING)]),
		]
