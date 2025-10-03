from pydantic import BaseModel


class CustomerBase(BaseModel):
	user_id: str
	name: str | None = None
	email: str | None = None
	plan: str | None = None


class TicketBase(BaseModel):
	ticket_id: str
	user_id: str
	subject: str
	description: str
	status: str = "open"
