from contextlib import asynccontextmanager
from datetime import timezone

from beanie import init_beanie
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient

# DAOs (Beanie)
from app.agents.models import MessageDAO, ThreadDAO

# Milvus bootstrap
from app.core.connectors.milvus_bootstrap import init_milvus
from app.customers.models import (
	AccountDAO,
	ComplianceDAO,
	CustomerDAO,
	SecurityDAO,
	TicketDAO,
)

# Seeder
from app.customers.seed import seed_customers
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
			# Agents
			ThreadDAO,
			MessageDAO,
			# Customers
			CustomerDAO,
			AccountDAO,
			ComplianceDAO,
			SecurityDAO,
			TicketDAO,
			# RAG
			FileDAO,
			ChunkDAO,
		],
	)
	logger.info("Beanie initialized successfully.")

	# 2) Seed
	try:
		await seed_customers()
	except Exception:
		logger.exception("Seeding customers failed (continuing).")

	# 3) Milvus
	try:
		await init_milvus()
		logger.info("Milvus bootstrap completed.")
	except Exception:
		logger.exception("Milvus bootstrap failed (continuing).")

	try:
		yield
	finally:
		client.close()
		logger.info("MongoDB connection closed.")
