from __future__ import annotations

import re

from fastapi import APIRouter
from pydantic import BaseModel

from gateway.core.config import get_settings
from gateway.core.store import Store

router = APIRouter(prefix="/api/v1/cache", tags=["cache"])


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\u0900-\u097F]+", " ", text.lower())).strip()


class CacheLookup(BaseModel):
    text: str
    language: str = "auto"


@router.post("/lookup")
def lookup(request: CacheLookup):
    """Starter implementation. Shivam: replace with exact + semantic retrieval."""
    settings = get_settings()
    store = Store(settings.database_path)
    key = normalize(request.text)
    entries = store.list_cache(100)
    for item in entries:
        if item["normalized"] == key:
            return {"hit": True, "match_type": "exact", "similarity": 1.0, "matched_question": item["question"], "answer": item["answer"], "source": item["source"], "cache_id": item["id"]}
    return {"hit": False, "match_type": "none", "similarity": 0.0, "matched_question": None, "answer": None, "source": None, "note": "Replace with semantic matching and cache management."}


@router.get("/entries")
def entries():
    settings = get_settings()
    return {"items": Store(settings.database_path).list_cache(100)}
