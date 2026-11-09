from __future__ import annotations

from collections import Counter

from fastapi import APIRouter
from pydantic import BaseModel

from gateway.core.config import get_settings
from gateway.core.store import Store
from gateway.modules.m1_pipeline.hinglish import code_mix_ratio
from gateway.tokenizer import TokenCounter

router = APIRouter(prefix="/api/v1/insights", tags=["insights"])
counter = TokenCounter()


class TokenizeRequest(BaseModel):
    text: str
    variants: dict[str, str] | None = None


@router.post("/tokenize")
def tokenize(request: TokenizeRequest):
    variants = request.variants or {"input": request.text}
    return {
        "backend": counter.backend,
        "items": [{"label": k, "text": v, "tokens": counter.count(v), "chars": len(v)} for k, v in variants.items()],
        "note": "Reference tokenization for comparison. Provider usage may differ.",
    }


@router.get("/summary")
def summary():
    settings = get_settings()
    items = Store(settings.database_path).list_requests(200)
    languages = Counter(i["language"] for i in items)
    return {
        "requests": len(items),
        "languages": dict(languages),
        "average_code_mix": round(sum(code_mix_ratio(i["text"]) for i in items) / len(items), 4) if items else 0,
        "note": "Aman: add PCA, clustering, request history charts and the length-prediction model here.",
    }
