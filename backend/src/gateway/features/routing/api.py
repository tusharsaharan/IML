from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .service import get_service, load_metrics_artifact

router = APIRouter(prefix="/api/v1/routing", tags=["routing"])


class RoutingRequest(BaseModel):
    text: str
    compressed_text: str | None = None
    policy: Literal["economy", "balanced", "quality"] = "balanced"


@router.post("/predict")
def predict(request: RoutingRequest):
    """Policy-aware routing from the trained CPU classifiers with a labelled fallback."""
    return get_service().predict(request.text, request.policy, request.compressed_text)


@router.get("/models")
def models():
    """Metrics artifact for the model-comparison table."""
    try:
        return load_metrics_artifact()
    except (OSError, ValueError) as exc:
        raise HTTPException(
            404,
            "Routing metrics artifact not found or unreadable. "
            "Run python backend/scripts/train_router.py.",
        ) from exc
