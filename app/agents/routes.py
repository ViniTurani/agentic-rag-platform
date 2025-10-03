from fastapi import APIRouter, HTTPException
from loguru import logger

from app.agents.controllers import read_thread_by_id, run_agents

from .schemas import RunRequest, ThreadOut

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/run", response_model=ThreadOut)
async def run(payload: RunRequest) -> ThreadOut:
	try:
		thread_out = await run_agents(
			message=payload.message,
			user_id=payload.user_id,
			thread_id=payload.thread_id,
		)
		return thread_out
	except Exception as e:
		logger.exception("Error on agents runner")
		raise HTTPException(status_code=500, detail=str(e))


@router.get("/threads/{thread_id}", response_model=ThreadOut)
async def get_thread(thread_id: str) -> ThreadOut:
	try:
		data = await read_thread_by_id(thread_id)
		if not data:
			raise HTTPException(status_code=404, detail="Thread not found")

		return data
	except HTTPException:
		raise
	except Exception as e:
		logger.exception("Error on GET /agents/threads/{thread_id}")
		raise HTTPException(status_code=500, detail=str(e))
