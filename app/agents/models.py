from typing import Literal

from beanie import Document, PydanticObjectId
from app.core.db.timestamps import TimestampingMixin

from .schemas import Message, Thread


class ThreadDAO(Thread, TimestampingMixin, Document):
	status: Literal["active", "archived", "closed"] = "active"
	created_by: str
	messages: list[PydanticObjectId] = []

	class Settings:
		name = "threads"


class MessageDAO(Message, TimestampingMixin, Document):
	thread_id: PydanticObjectId

	class Settings:
		name = "messages"
