from typing import Literal, Optional

from pydantic import BaseModel, Field


class Message(BaseModel):
	role: Literal["user", "assistant", "system", "tool"]
	content: str
	name: Optional[str] = None


class Thread(BaseModel):
	messages: list[Message] = Field(default_factory=list)
	created_by: str


class ThreadOut(Thread):
	thread_id: str
	created_at: str
	updated_at: str


class RunRequest(BaseModel):
	message: str = Field(..., description="User message")
	user_id: str = Field(..., description="User identifier")
	thread_id: Optional[str] = Field(None, description="Optional Session/Thread")
