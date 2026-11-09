from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from gateway.modules.m1_pipeline.hinglish import code_mix_ratio, language_group
from gateway.tokenizer import TokenCounter

router = APIRouter(prefix="/api/v1/routing", tags=["routing"])
counter = TokenCounter()


class RoutingRequest(BaseModel):
    text: str
    compressed_text: str | None = None
    policy: str = "balanced"


@router.post("/predict")
def predict(request: RoutingRequest):
    """Starter implementation. Rakesh: replace with trained router comparison and policy controls."""
    text = request.compressed_text or request.text
    features = {
        "token_count": counter.count(text),
        "char_count": len(text),
        "word_count": len(text.split()),
        "code_mix_ratio": code_mix_ratio(text),
        "language_group": language_group(text),
    }
    score = min(1.0, 0.15 + features["code_mix_ratio"] * 0.45 + min(features["token_count"], 120) / 220)
    threshold = {"economy": 0.7, "balanced": 0.5, "quality": 0.3}.get(request.policy, 0.5)
    tier = "strong" if score >= threshold else "cheap"
    return {
        "selected_tier": tier,
        "selected_model_label": "Strong model" if tier == "strong" else "Economy model",
        "score": round(score, 4),
        "threshold": threshold,
        "policy": request.policy,
        "features": features,
        "model_scores": {"starter-logistic": round(score, 4), "starter-random-forest": round(min(1, score + 0.03), 4), "starter-mlp": round(max(0, score - 0.02), 4)},
        "explanation": [f"Language group: {features['language_group']}", f"Code-mix ratio: {features['code_mix_ratio']:.2f}", f"Token count: {features['token_count']}"],
        "note": "Replace with trained classifiers and evaluation artifacts.",
    }
