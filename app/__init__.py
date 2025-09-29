from fastapi import FastAPI

from .health import router as health_router
from .rag import rag_router
from .metrics import metrics_router


def create_app() -> FastAPI:
    app = FastAPI(title="API", version="0.1.0", separate_input_output_schemas=False)
    app.include_router(health_router, tags=["health"])
    app.include_router(rag_router, tags=["rag"])
    app.include_router(metrics_router, tags=["metrics"])

    return app
