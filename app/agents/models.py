from datetime import datetime

from app.rag.models import Document


class RunLogDAO(Document):
	session_id: str
	agent: str
	user_id: str
	input_text: str
	output_text: str
	trace_id: str | None = None
	created_at: datetime = datetime.utcnow()

	@classmethod
	def get_collection_name(cls) -> str:
		return "agent_runs"


class TicketDAO(Document):
	ticket_id: str
	user_id: str
	subject: str
	description: str
	status: str = "open"
	created_at: datetime = datetime.utcnow()

	@classmethod
	def get_collection_name(cls) -> str:
		return "tickets"


class CustomerDAO(Document):
	user_id: str
	name: str | None = None
	email: str | None = None
	plan: str | None = None
	updated_at: datetime = datetime.utcnow()

	@classmethod
	def get_collection_name(cls) -> str:
		return "customers"
