from fastapi import FastAPI

from app.dependencies import lifespan

from .agents import agents_router
from .health import router as health_router
from .metrics import metrics_router
from .rag import rag_router


def create_app() -> FastAPI:
	app = FastAPI(
		title="API",
		version="0.1.0",
		separate_input_output_schemas=False,
		lifespan=lifespan,
	)

	app.include_router(health_router, tags=["health"])
	app.include_router(rag_router, tags=["rag"])
	app.include_router(metrics_router, tags=["metrics"])
	app.include_router(agents_router, tags=["agents"])

	return app
