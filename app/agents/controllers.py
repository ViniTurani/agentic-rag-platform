from __future__ import annotations

from loguru import logger

from app.agents.models import RunLogDAO
from app.agents.schemas import RunResponse
from app.core.agents.engine import get_engine
from app.core.connectors.mongo import MongoHelper


async def run_agents(
	message: str, user_id: str, session_id: str | None = None
) -> RunResponse:
	engine = get_engine()
	result = await engine.run(message=message, user_id=user_id, session_id=session_id)

	output = result.final_output or ""
	trace_id = getattr(result, "trace_id", None)

	# log no Mongo (padrão DAO)
	try:
		MongoHelper().insert_one(
			RunLogDAO(
				session_id=session_id or f"swarm:{user_id}",
				agent=engine.entry.name,
				user_id=user_id,
				input_text=message,
				output_text=output,
				trace_id=trace_id,
			).model_dump(),
			RunLogDAO,  # type: ignore
		)
	except Exception:
		logger.exception("failed to log agent run")

	return RunResponse(output=output, trace_id=trace_id)
