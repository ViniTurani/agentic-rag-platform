from datetime import datetime, timezone

from loguru import logger

from .models import AccountDAO, ComplianceDAO, CustomerDAO, SecurityDAO, TicketDAO


def _utc_now() -> datetime:
	return datetime.now(timezone.utc)


async def seed_customers() -> None:
	"""
	Create/update some customers (idempotent) for support agent testing.
	"""
	samples = [
		{
			"user_id": "client789",
			"name": "João Silva",
			"email": "joao.silva@example.com",
			"plan": "pro",
			"account": {
				"balance_cents": 523_450,
				"holds_cents": 5_000,
				"currency": "BRL",
			},
			"compliance": {
				"kyc_status": "verified",
				"risk_score": 12,
				"transfer_enabled": True,
				"transfer_block_reason": None,
			},
			"security": {
				"login_disabled": False,
				"failed_attempts": 1,
				"last_login_at": _utc_now(),
				"two_factor_enabled": True,
			},
			"tickets": [],
		},
		{
			"user_id": "client123",
			"name": "Maria Oliveira",
			"email": "maria.oliveira@example.com",
			"plan": "basic",
			"account": {"balance_cents": 12_340, "holds_cents": 0, "currency": "BRL"},
			"compliance": {
				"kyc_status": "pending",
				"risk_score": 48,
				"transfer_enabled": False,
				"transfer_block_reason": "KYC documents pending review",
			},
			"security": {
				"login_disabled": True,
				"failed_attempts": 5,
				"last_login_at": _utc_now(),
				"two_factor_enabled": False,
			},
			"tickets": [
				{
					"ticket_id": "TCK-1234ABCD",
					"subject": "Transfer blocked",
					"description": "Customer reports unable to transfer funds",
					"status": "open",
				}
			],
		},
	]

	upserts = {
		"customers": 0,
		"accounts": 0,
		"compliance": 0,
		"security": 0,
		"tickets": 0,
	}

	for s in samples:
		user_id = s["user_id"]

		# Customer
		cust = await CustomerDAO.find_one(CustomerDAO.user_id == user_id)
		if cust:
			cust.name = s["name"]
			cust.email = s["email"]
			cust.plan = s["plan"]
			await cust.save()
		else:
			await CustomerDAO(
				user_id=user_id, name=s["name"], email=s["email"], plan=s["plan"]
			).insert()
		upserts["customers"] += 1

		# Account
		acc = await AccountDAO.find_one(AccountDAO.user_id == user_id)
		if acc:
			acc.balance_cents = s["account"]["balance_cents"]
			acc.holds_cents = s["account"]["holds_cents"]
			acc.currency = s["account"]["currency"]
			await acc.save()
		else:
			await AccountDAO(user_id=user_id, **s["account"]).insert()
		upserts["accounts"] += 1

		# Compliance
		comp = await ComplianceDAO.find_one(ComplianceDAO.user_id == user_id)
		if comp:
			comp.kyc_status = s["compliance"]["kyc_status"]
			comp.risk_score = s["compliance"]["risk_score"]
			comp.transfer_enabled = s["compliance"]["transfer_enabled"]
			comp.transfer_block_reason = s["compliance"]["transfer_block_reason"]
			await comp.save()
		else:
			await ComplianceDAO(user_id=user_id, **s["compliance"]).insert()
		upserts["compliance"] += 1

		# Security
		sec = await SecurityDAO.find_one(SecurityDAO.user_id == user_id)
		if sec:
			sec.login_disabled = s["security"]["login_disabled"]
			sec.failed_attempts = s["security"]["failed_attempts"]
			sec.last_login_at = s["security"]["last_login_at"]
			sec.two_factor_enabled = s["security"]["two_factor_enabled"]
			await sec.save()
		else:
			await SecurityDAO(user_id=user_id, **s["security"]).insert()
		upserts["security"] += 1

		# Tickets
		for tk in s["tickets"]:
			existing = await TicketDAO.find_one(TicketDAO.ticket_id == tk["ticket_id"])
			if not existing:
				await TicketDAO(user_id=user_id, **tk).insert()
				upserts["tickets"] += 1

	logger.info(
		"Seed customers done: "
		f"customers={upserts['customers']} accounts={upserts['accounts']} "
		f"compliance={upserts['compliance']} security={upserts['security']} "
		f"tickets={upserts['tickets']}"
	)
