from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .controllers import get_ui_metrics

router = APIRouter()


@router.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/ui-metrics")
def ui_metrics():
    """Compact JSON for Streamlit: counters + per-stage latency stats."""
    return get_ui_metrics()
