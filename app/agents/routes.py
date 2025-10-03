from __future__ import annotations

from fastapi import APIRouter, HTTPException
from loguru import logger

from app.agents.controllers import read_thread_by_id, run_agents
from app.agents.schemas import (
	RunRequest,
	ThreadOut,
)

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/run", response_model=ThreadOut)
async def run(payload: RunRequest) -> ThreadOut:
	try:
		return await run_agents(
			message=payload.message,
			user_id=payload.user_id,
			thread_id=payload.thread_id,
		)
	except HTTPException:
		raise
	except Exception as e:
		logger.exception("Error on /agents/run")
		raise HTTPException(status_code=500, detail=str(e))


@router.get("/threads/{thread_id}", response_model=ThreadOut)
async def get_thread(thread_id: str) -> ThreadOut:
	try:
		return await read_thread_by_id(thread_id)
	except HTTPException:
		raise
	except Exception as e:
		logger.exception("Error on GET /agents/threads/{thread_id}")
		raise HTTPException(status_code=500, detail=str(e))
