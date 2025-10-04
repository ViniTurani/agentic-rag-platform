from typing import Any
from uuid import uuid4

from loguru import logger
from pydantic import BaseModel, Field

from agents import RunContextWrapper
from app.customers.models import TicketDAO
from app.customers.schemas import TicketOut


class Arguments(BaseModel):
	user_id: str = Field(..., description="The user ID of the customer")
	subject: str = Field(..., description="The subject of the ticket")
	description: str = Field(..., description="The description of the ticket")


async def create_ticket(ctx: RunContextWrapper[Any], args: str) -> TicketOut | None:
	"""
	Creates a support ticket for the given user.
	"""
	try:
		logger.info(f"Creating ticket with args: {args}")

		parsed = Arguments.model_validate_json(args)
		user_id = parsed.user_id
		subject = parsed.subject
		description = parsed.description

		ticket_id = f"TCK-{uuid4().hex[:8].upper()}"
		tk = TicketDAO(
			ticket_id=ticket_id,
			user_id=user_id,
			subject=subject,
			description=description,
			status="open",
		)
		await tk.insert()

		logger.debug(f"Created ticket: {tk}")

		return TicketOut(**tk.model_dump(exclude={"id"}), id=str(tk.id))
	except Exception as e:
		logger.error(f"Error in create_ticket: {e}")
		return None
