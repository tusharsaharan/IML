from __future__ import annotations

import re
import sqlite3
import unicodedata
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from gateway.core.config import get_settings
from gateway.core.store import Store
from gateway.modules.m12_semantic.embeddings import HASH_THRESHOLD, SemanticEmbedder

router = APIRouter(prefix="/api/v1/cache", tags=["cache"])
_embedder = SemanticEmbedder(use_st=False)
_HINGLISH_EQUIVALENTS = {
    "kitab": "book", "kitabein": "books", "pustak": "book",
    "kaise": "how", "kese": "how", "kaisa": "how",
    "karu": "do", "karoon": "do", "karo": "do", "karna": "do", "krun": "do", "krna": "do",
    "ki": "", "ka": "", "ke": "", "ko": "", "kya": "what", "hai": "is", "hain": "are",
    "meri": "my", "mera": "my", "mere": "my", "chahiye": "need",
}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\u0900-\u097f]+", " ", text)).strip()


class CacheLookup(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    language: str = "auto"


class CacheEntryInput(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    answer: str = Field(min_length=1, max_length=6000)
    language: str = Field(default="auto", max_length=32)


DEMO_FAQS = [
    {
        "question": "How can I renew a library book?",
        "answer": "To renew a library book, sign in to the library portal, open your issued items, and choose Renew before the due date. If the book is reserved by another student or you have reached the renewal limit, visit the help desk.",
        "language": "en",
    },
    {
        "question": "How do I connect to campus Wi-Fi?",
        "answer": "Connect to the official campus Wi-Fi, sign in with your institute account, and check that your device date and time are correct. If the login page does not appear, forget the network and reconnect. Contact IT support if it keeps failing.",
        "language": "en",
    },
    {
        "question": "Where can I find the assignment deadline?",
        "answer": "Assignment deadlines are listed on the course page. Submit before the listed time and keep the confirmation receipt or upload timestamp. Contact course staff before the deadline if you expect a delay.",
        "language": "en",
    },
]


def _cache_store() -> Store:
    settings = get_settings()
    store = Store(settings.database_path)
    with store.connect() as db:
        db.execute(
            """create table if not exists cache_lookup_events (
                id integer primary key autoincrement,
                created_at text not null,
                match_type text not null
            )"""
        )
    return store


def _record_lookup(match_type: str) -> None:
    settings = get_settings()
    with sqlite3.connect(settings.database_path) as db:
        db.execute(
            "insert into cache_lookup_events(created_at, match_type) values (?, ?)",
            (datetime.now(timezone.utc).isoformat(), match_type),
        )


def _similarity(a: str, b: str) -> float:
    def canonicalize(text: str) -> str:
        words = normalize(text).split()
        return " ".join(_HINGLISH_EQUIVALENTS.get(word, word) for word in words if _HINGLISH_EQUIVALENTS.get(word, word))

    return _embedder.similarity(canonicalize(a), canonicalize(b))


@router.post("/lookup")
def lookup(request: CacheLookup):
    store = _cache_store()
    key = normalize(request.text)
    if not key:
        raise HTTPException(status_code=422, detail="Question must contain letters or numbers.")

    entries = store.list_cache(500)
    for item in entries:
        if item["normalized"] == key:
            _record_lookup("exact")
            return {
                "hit": True, "match_type": "exact", "similarity": 1.0,
                "matched_question": item["question"], "answer": item["answer"],
                "source": item["source"], "cache_id": item["id"],
                "note": "Exact match after case, punctuation and whitespace normalization.",
            }

    best: dict | None = None
    best_score = 0.0
    for item in entries:
        score = _similarity(request.text, item["question"])
        if score > best_score:
            best, best_score = item, score

    threshold = min(get_settings().cache_threshold, HASH_THRESHOLD)
    if best is not None and best_score >= threshold:
        _record_lookup("semantic")
        return {
            "hit": True, "match_type": "semantic", "similarity": round(best_score, 4),
            "matched_question": best["question"], "answer": best["answer"],
            "source": best["source"], "cache_id": best["id"], "threshold": threshold,
            "note": "Near-match: review the matched question and similarity before reusing this answer.",
        }

    _record_lookup("miss")
    return {
        "hit": False, "match_type": "none", "similarity": round(best_score, 4),
        "matched_question": best["question"] if best else None, "answer": None,
        "source": best["source"] if best else None, "cache_id": best["id"] if best else None,
        "threshold": threshold,
        "note": "No safe cache match. The closest question is shown for review only.",
    }


@router.get("/entries")
def entries():
    return {"items": _cache_store().list_cache(500)}


@router.post("/entries", status_code=201)
def add_entry(request: CacheEntryInput):
    normalized = normalize(request.question)
    if not normalized:
        raise HTTPException(status_code=422, detail="Question must contain letters or numbers.")
    store = _cache_store()
    existing = next((item for item in store.list_cache(500) if item["normalized"] == normalized), None)
    if existing:
        raise HTTPException(status_code=409, detail="An entry with this normalized question already exists.")
    item_id = store.put_cache(request.question.strip(), normalized, request.answer.strip(), request.language, "authored")
    return {"id": item_id, "question": request.question.strip(), "answer": request.answer.strip(), "language": request.language, "source": "authored"}


@router.post("/seed")
def seed_demo_faqs():
    store = _cache_store()
    existing = {item["normalized"] for item in store.list_cache(500)}
    added = 0
    for faq in DEMO_FAQS:
        normalized = normalize(faq["question"])
        if normalized not in existing:
            store.put_cache(faq["question"], normalized, faq["answer"], faq["language"], "authored-demo")
            existing.add(normalized)
            added += 1
    return {"added": added, "total": len(store.list_cache(500)), "source": "authored-demo"}


@router.delete("/entries/{entry_id}")
def delete_entry(entry_id: int):
    settings = get_settings()
    with sqlite3.connect(settings.database_path) as db:
        cursor = db.execute("delete from cache_entries where id = ?", (entry_id,))
    if not cursor.rowcount:
        raise HTTPException(status_code=404, detail="Cache entry not found.")
    return {"deleted": entry_id}


@router.delete("/entries")
def clear_entries():
    settings = get_settings()
    with sqlite3.connect(settings.database_path) as db:
        cursor = db.execute("delete from cache_entries")
    return {"deleted": cursor.rowcount}


@router.get("/stats")
def stats():
    store = _cache_store()
    with store.connect() as db:
        rows = db.execute("select match_type, count(*) as count from cache_lookup_events group by match_type").fetchall()
    counts = {row["match_type"]: row["count"] for row in rows}
    exact = counts.get("exact", 0)
    semantic = counts.get("semantic", 0)
    misses = counts.get("miss", 0)
    return {"total_lookups": exact + semantic + misses, "exact_hits": exact, "semantic_hits": semantic, "misses": misses}
