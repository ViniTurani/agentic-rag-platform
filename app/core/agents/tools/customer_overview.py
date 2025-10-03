from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from agents import RunContextWrapper
from app.customers.models import (
	AccountDAO,
	ComplianceDAO,
	CustomerDAO,
	SecurityDAO,
	TicketDAO,
)
from app.customers.schemas import (
	AccountOut,
	ComplianceOut,
	CustomerOut,
	SecurityOut,
	SupportOverview,
	TicketOut,
)


class Arguments(BaseModel):
	user_id: str = Field(..., description="The user ID of the customer")


async def get_support_overview(
	ctx: RunContextWrapper[Any],
	args: str,
) -> SupportOverview:
	"""
	Returns a consolidated customer overview for support:
	- Profile (Customer)
	- Account (balance/holds)
	- Compliance/Transfers (KYC/risk/transfer_enabled/reason)
	- Security (logins, attempts, 2FA)
	- Open tickets
	"""
	try:
		logger.info(f"get_support_overview called with args: {args}")
		parsed = Arguments.model_validate_json(args)
		user_id = parsed.user_id
		logger.debug(f"Parsed user_id: {user_id}")

		customer = await CustomerDAO.find_one(CustomerDAO.user_id == user_id)
		acc = await AccountDAO.find_one(AccountDAO.user_id == user_id)
		comp = await ComplianceDAO.find_one(ComplianceDAO.user_id == user_id)
		sec = await SecurityDAO.find_one(SecurityDAO.user_id == user_id)
		tks = await TicketDAO.find(
			{"user_id": user_id, "status": {"$in": ["pending", "open"]}}
		).to_list()

		logger.debug(
			"Database tasks completed",
		)
		logger.debug(
			f"Found: customer={'yes' if customer else 'no'}, account={'yes' if acc else 'no'}, "
			f"compliance={'yes' if comp else 'no'}, security={'yes' if sec else 'no'}"
		)
		logger.debug(f"Number of ticket records fetched: {len(tks or [])}")

		user_out = CustomerOut(**customer.model_dump()) if customer else None
		account_out = AccountOut(**acc.model_dump()) if acc else None
		compliance_out = ComplianceOut(**comp.model_dump()) if comp else None
		security_out = SecurityOut(**sec.model_dump()) if sec else None

		open_tickets = []
		for tk in tks or []:
			tk: TicketDAO
			ticket_id = tk.ticket_id
			logger.debug(f"Processing ticket id={ticket_id}")
			open_tickets.append(
				TicketOut(**tk.model_dump(exclude={"id"}), id=str(tk.id))
			)

		result = SupportOverview(
			user=user_out,
			account=account_out,
			compliance=compliance_out,
			security=security_out,
			open_tickets=open_tickets,
		)
		logger.info(
			f"Returning SupportOverview for user_id={user_id} "
			f"(user_found={'yes' if user_out else 'no'}, tickets={len(open_tickets)})"
		)
		return result
	except Exception:
		logger.exception("Error in get_support_overview")
		raise
