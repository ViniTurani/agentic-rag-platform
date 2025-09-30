from datetime import datetime

from pydantic import BaseModel

from app.rag.schemas import Chunk


class Document(BaseModel):
	@classmethod
	def get_collection_name(cls) -> str:
		raise NotImplementedError()


class ChunkDAO(Chunk, Document):
	@classmethod
	def get_collection_name(cls) -> str:
		return "chunks"


class FileDAO(Document):
	file_id: str
	file_hash: str
	filename: str | None
	title: str | None
	content: str
	total_pages: int
	size_bytes: int
	mime: str
	created_at: datetime

	@classmethod
	def get_collection_name(cls) -> str:
		return "files"
