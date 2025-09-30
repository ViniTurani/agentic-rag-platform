from __future__ import annotations

import json
from typing import Any

from loguru import logger

from agents import RunContextWrapper
from app.agents.models import CustomerDAO, TicketDAO
from app.core.connectors.mongo import MongoHelper


async def get_customer_impl(ctx: RunContextWrapper[Any], args_json: str) -> str:
	"""
	Retorna os dados do cliente como JSON (string). Procura por user_id.
	"""
	try:
		args = json.loads(args_json or "{}")
		user_id = str(args.get("user_id", "")).strip()
		if not user_id:
			return "{}"
		db = MongoHelper()
		doc = (
			db.read_one(CustomerDAO, {"user_id": user_id}, projection={"_id": 0}) or {}
		)
		return json.dumps(doc, ensure_ascii=False)
	except Exception:
		logger.exception("get_customer_impl failed")
		return "{}"


async def create_ticket_impl(ctx: RunContextWrapper[Any], args_json: str) -> str:
	"""
	Cria um ticket e retorna {"ticket_id": "..."} como JSON (string).
	"""
	try:
		args = json.loads(args_json or "{}")
		user_id = str(args.get("user_id", "")).strip()
		subject = str(args.get("subject", "")).strip()
		description = str(args.get("description", "")).strip()
		if not (user_id and subject and description):
			return json.dumps({"error": "missing fields"}, ensure_ascii=False)

		db = MongoHelper()
		payload = {
			"ticket_id": f"TCK-{hash((user_id, subject)) & 0xFFFF:04X}",
			"user_id": user_id,
			"subject": subject,
			"description": description,
			"status": "open",
		}
		db.insert_one(payload, TicketDAO)
		return json.dumps({"ticket_id": payload["ticket_id"]}, ensure_ascii=False)
	except Exception:
		logger.exception("create_ticket_impl failed")
		return json.dumps({"error": "internal"}, ensure_ascii=False)
