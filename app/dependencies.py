from contextlib import asynccontextmanager
from datetime import timezone

from beanie import init_beanie
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient

from app.agents.models import MessageDAO, ThreadDAO
from app.core.connectors.milvus_bootstrap import init_milvus
from app.customers.models import CustomerDAO, TicketDAO
from app.rag.models import ChunkDAO, FileDAO
from app.settings import Settings


@asynccontextmanager
async def lifespan(app):
	settings = Settings.get()

	logger.info("Initializing MongoDB/Beanie...")
	client = AsyncIOMotorClient(
		settings.MONGO_URI,
		tz_aware=True,
		tzinfo=timezone.utc,
	)

	db = client[settings.MONGO_DB]
	await init_beanie(
		database=db,  # type: ignore
		document_models=[
			ThreadDAO,
			MessageDAO,
			CustomerDAO,
			TicketDAO,
			FileDAO,
			ChunkDAO,
		],
	)
	logger.info("Beanie initialized successfully.")

	# 2) Milvus
	try:
		await init_milvus()
		logger.info("Milvus bootstrap completed.")
	except Exception:
		logger.exception("Milvus bootstrap failed (the API will continue to run).")

	try:
		yield
	finally:
		client.close()
		logger.info("MongoDB connection closed.")
