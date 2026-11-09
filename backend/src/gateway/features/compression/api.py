from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from gateway.tokenizer import TokenCounter

router = APIRouter(prefix="/api/v1/compression", tags=["compression"])
counter = TokenCounter()


class CompressionRequest(BaseModel):
    text: str = Field(min_length=1)
    method: str = "heuristic"
    budget: float = Field(default=0.6, ge=0.1, le=1.0)


@router.post("/analyze")
def analyze(request: CompressionRequest):
    """Starter implementation. Tushar: replace with imported compressor + budget control."""
    words = request.text.split()
    keep = max(1, int(len(words) * request.budget))
    compressed = " ".join(words[:keep]) if words else request.text
    original_tokens = counter.count(request.text)
    compressed_tokens = counter.count(compressed)
    return {
        "original": request.text,
        "compressed": compressed,
        "method": f"starter-{request.method}",
        "budget": request.budget,
        "original_tokens": original_tokens,
        "compressed_tokens": compressed_tokens,
        "saved_tokens": max(0, original_tokens - compressed_tokens),
        "removed_spans": [{"text": w, "reason": "starter truncation"} for w in words[keep:][:12]],
        "protected_spans": [],
        "note": "Replace this starter with the imported CRF/heuristic compressor and protected spans.",
    }
