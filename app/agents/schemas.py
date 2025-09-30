from typing import Any, Optional

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
	message: str = Field(..., description="Mensagem do usuario")
	user_id: str = Field(..., description="Identificador do usuario")
	session_id: Optional[str] = Field(None, description="Sessao opcional")


class RunResponse(BaseModel):
	output: str
	trace_id: Optional[str] = None
	items: Optional[Any] = None
