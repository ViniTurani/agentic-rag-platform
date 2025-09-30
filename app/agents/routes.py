from fastapi import APIRouter

from app.agents.controllers import run_agents
from app.agents.schemas import RunRequest, RunResponse

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/run", response_model=RunResponse)
async def run(payload: RunRequest) -> RunResponse:
	return await run_agents(
		message=payload.message,
		user_id=payload.user_id,
		session_id=payload.session_id,
	)
