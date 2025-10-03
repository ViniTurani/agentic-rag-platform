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
	Executa o agente e persiste as mensagens/threads.
	- Se thread_id nao for informado, cria uma nova thread.
	- Se informado e nao existir, cria uma nova (logando um warning).
	- Salva a msg do usuario e a msg do assistente como registros MessageDAO.
	- Retorna: (output_text, thread_id)
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

	# 3) Executa o engine
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

	assistant_msg = MessageDAO(
		thread_id=thread.id,
		role="assistant",
		content=result.final_output,
		name=result.last_agent.name,
	)
	await assistant_msg.insert()

	if not assistant_msg.id:
		raise HTTPException(
			status_code=404, detail="Failed to store assistant message."
		)

	thread.messages.append(assistant_msg.id)
	await thread.save()

	logger.info(f"Run complete: thread={thread_id}")
	return await read_thread_by_id(thread_id)


async def read_thread_by_id(thread_id: str) -> ThreadOut:
	"""
	Le a thread + mensagens por id para retornar.
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
