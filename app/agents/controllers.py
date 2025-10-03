from typing import Optional

from beanie import PydanticObjectId
from fastapi import HTTPException
from loguru import logger

from app.core.agents.engine import get_engine

from .models import MessageDAO, ThreadDAO
from .schemas import Message, ThreadOut


async def run_agents(
	message: str,
	user_id: str,
	thread_id: Optional[str] = None,
) -> ThreadOut:
	"""
	Execute the agent and persist the messages/threads.
	- If thread_id is not provided, create a new thread.
	- If provided and doesn't exist, create a new one (logging a warning).
	- Save the user message and assistant message as MessageDAO records.
	- Returns: ThreadOut object with complete thread information.
	"""

	thread: ThreadDAO | None = None
	if thread_id:
		try:
			thread_oid = PydanticObjectId(thread_id)
			thread = await ThreadDAO.get(thread_oid)
			if thread is None:
				logger.warning(f"Thread {thread_id} not found. Creating a new one.")
		except Exception:
			logger.exception("Invalid thread_id received. Creating a new thread.")
			thread = None

	if thread is None:
		thread = ThreadDAO(
			created_by=user_id,
		)
		await thread.insert()
		thread_id = str(thread.id)
		logger.info(f"Created new thread {thread_id} for user {user_id}")
	else:
		thread_id = str(thread.id)

	if not thread.id:
		raise ValueError("Failed to store or retrieve thread ID.")

	user_msg = MessageDAO(
		thread_id=thread.id,
		role="user",
		content=message,
		name=user_id,
	)

	await user_msg.insert()
	if not user_msg.id:
		raise ValueError("Failed to store user message.")

	thread.messages.append(user_msg.id)
	await thread.save()

	# 3) Execute the engine
	engine = get_engine()
	logger.info(f"Running agent for thread={thread_id} user={user_id}")
	try:
		result = await engine.run(
			message=message,
			user_id=user_id,
			thread_id=thread_id,
		)
	except Exception as e:
		logger.exception("Error running agents engine")
		raise HTTPException(status_code=500, detail=str(e))

	messages = []
	for x in result.raw_responses:
		logger.debug(f"Agent response: {x}")

		try:
			content = x.output[-1].content[-1].text  # type: ignore
		except Exception:
			content = str(x.output)

		assistant_msg = MessageDAO(
			thread_id=thread.id,
			role="assistant",
			content=content,
			name=result.last_agent.name,
		)
		await assistant_msg.insert()

		if not assistant_msg.id:
			raise HTTPException(
				status_code=404, detail="Failed to store assistant message."
			)

		messages.append(assistant_msg)

	thread.messages.extend([msg.id for msg in messages])
	await thread.save()

	logger.info(f"Run complete: thread={thread_id}")
	return await read_thread_by_id(thread_id)


async def read_thread_by_id(thread_id: str) -> ThreadOut:
	"""
	Read a thread + messages by id to return.
	"""
	try:
		oid = PydanticObjectId(thread_id)
	except Exception:
		logger.error(f"Invalid thread_id: {thread_id}")
		raise

	thread = await ThreadDAO.get(oid)
	if not thread:
		logger.warning(f"Thread not found: {thread_id}")
		raise ValueError("Thread not found")

	msgs = (
		await MessageDAO.find(MessageDAO.thread_id == oid).sort("+created_at").to_list()
	)

	messages = [
		Message(
			thread_id=str(m.id),
			role=m.role,
			content=m.content,
			name=m.name,
		)
		for m in msgs
	]

	return ThreadOut(
		thread_id=str(thread.id),
		metadata={"thread.status": thread.status},
		created_by=thread.created_by,
		created_at=thread.created_at.isoformat(),
		updated_at=thread.updated_at.isoformat(),
		messages=messages,
	)
