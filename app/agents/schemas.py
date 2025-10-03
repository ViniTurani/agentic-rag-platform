from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class Message(BaseModel):
	thread_id: str
	role: Literal["user", "assistant", "system", "tool"]
	content: str
	name: str | None = None


class Thread(BaseModel):
	messages: list[Message] = Field(default_factory=list)
	created_by: str


class ThreadOut(BaseModel):
	thread_id: str
	metadata: dict[str, Any] | None
	created_at: str
	updated_at: str
	messages: list[Message]
	created_by: str


class RunRequest(BaseModel):
	thread_id: Optional[str] = Field(None, description="Sessao/Thread opcional")
	message: str = Field(..., description="Mensagem do usuario")
	user_id: str = Field(..., description="Identificador do usuario")
