from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from datetime import datetime, timedelta, timezone

import numpy as np
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from gateway.core.config import get_settings
from gateway.core.providers import Provider
from gateway.core.store import Store
from gateway.features.cache.redis_index import RedisExactIndex
from gateway.features.cache.settings import CacheSettings, get_cache_settings
from gateway.modules.m12_semantic.embeddings import SemanticEmbedder

router = APIRouter(prefix="/api/v1/cache", tags=["cache"])
_embedder = SemanticEmbedder(use_st=False)
_HINGLISH_EQUIVALENTS = {
    "kitab": "book", "kitabein": "books", "pustak": "book",
    "kaise": "how", "kese": "how", "kaisa": "how",
    "karu": "do", "karoon": "do", "karo": "do", "karna": "do", "krun": "do", "krna": "do",
    "ki": "", "ka": "", "ke": "", "ko": "", "kya": "what", "hai": "is", "hain": "are",
    "meri": "my", "mera": "my", "mere": "my", "chahiye": "need",
    "किताब": "book", "किताबें": "books", "पुस्तक": "book", "पुस्तकालय": "library",
    "लाइब्रेरी": "library", "नवीनीकरण": "renewal", "रिन्यू": "renew",
    "कैसे": "how", "करूं": "do", "करूँ": "do", "करना": "do", "की": "", "का": "", "के": "",
    "है": "is", "हैं": "are", "मेरा": "my", "मेरी": "my",
}
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b")
_URL_RE = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
_ID_RE = re.compile(r"\b(?:student|account|order|ticket|roll|reference)\s*(?:id|number|no\.?|#)\s*[:#-]?\s*[a-z0-9-]{4,}\b", re.IGNORECASE)
_PRIVATE_CONTEXT_RE = re.compile(r"\b(?:my|mera|meri)\s+(?:password|otp|ssn|social security|date of birth|dob)\b", re.IGNORECASE)
_SCOPE_RE = re.compile(r"^[A-Za-z0-9:_-]{1,128}$")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\u0900-\u097f]+", " ", text)).strip()


class CacheLookup(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    language: str = Field(default="auto", max_length=32)


class CacheAnswerRequest(CacheLookup):
    use_cache: bool = True
    store_answer: bool = True


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


def _hot_index(cache_settings: CacheSettings | None = None) -> RedisExactIndex:
    return RedisExactIndex((cache_settings or get_cache_settings()).redis_url)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _cache_store() -> Store:
    settings = get_settings()
    store = Store(settings.database_path)
    with store.connect() as db:
        db.executescript(
            """create table if not exists cache_lookup_events (
                    id integer primary key autoincrement,
                    created_at text not null,
                    match_type text not null,
                    scope_id text not null default 'public'
                );
                create table if not exists cache_entry_runtime (
                    entry_id integer primary key,
                    last_accessed_at text not null,
                    hit_count integer not null default 0,
                    expires_at text,
                    scope_id text not null default 'public',
                    normalized text not null default ''
                );
                create index if not exists idx_cache_entry_runtime_expiry
                    on cache_entry_runtime(expires_at);
                create index if not exists idx_cache_entries_normalized
                    on cache_entries(normalized);"""
        )
        event_columns = {row[1] for row in db.execute("pragma table_info(cache_lookup_events)")}
        if "scope_id" not in event_columns:
            db.execute("alter table cache_lookup_events add column scope_id text not null default 'public'")
        runtime_columns = {row[1] for row in db.execute("pragma table_info(cache_entry_runtime)")}
        if "scope_id" not in runtime_columns:
            db.execute("alter table cache_entry_runtime add column scope_id text not null default 'public'")
        if "normalized" not in runtime_columns:
            db.execute("alter table cache_entry_runtime add column normalized text not null default ''")
        db.execute(
            """update cache_entry_runtime set normalized=(
                   select normalized from cache_entries where cache_entries.id=cache_entry_runtime.entry_id
               ) where normalized=''"""
        )
        db.execute(
            "create unique index if not exists idx_cache_scope_normalized on cache_entry_runtime(scope_id,normalized) where normalized <> ''"
        )
        db.execute(
            """insert or ignore into cache_entry_runtime(entry_id,last_accessed_at,hit_count,expires_at,scope_id,normalized)
               select id,created_at,0,null,'public',normalized from cache_entries"""
        )
    _maintain_cache(store, get_cache_settings())
    return store


def _validated_scope(scope_id: str) -> str:
    if not _SCOPE_RE.fullmatch(scope_id):
        raise HTTPException(status_code=422, detail="Cache scope must use 1–128 letters, numbers, colons, underscores or hyphens.")
    return scope_id


def _entries_for_scope(store: Store, scope_id: str) -> list[dict]:
    items = store.list_cache(get_cache_settings().max_entries)
    with store.connect() as db:
        rows = db.execute("select entry_id from cache_entry_runtime where scope_id = ?", (scope_id,)).fetchall()
    scoped_ids = {row["entry_id"] for row in rows}
    return [item for item in items if item["id"] in scoped_ids]


def _maintain_cache(store: Store, cache_settings: CacheSettings) -> None:
    now = _now().isoformat()
    hot = _hot_index(cache_settings)
    with store.connect() as db:
        expired = db.execute(
            "select e.id,e.normalized,r.scope_id from cache_entries e join cache_entry_runtime r on r.entry_id=e.id where r.expires_at is not null and r.expires_at <= ?",
            (now,),
        ).fetchall()
        for row in expired:
            hot.delete(row["scope_id"], row["normalized"])
            db.execute("delete from cache_entries where id = ?", (row["id"],))
        if expired:
            db.executemany("delete from cache_entry_runtime where entry_id = ?", [(row["id"],) for row in expired])

        count = db.execute("select count(*) from cache_entries").fetchone()[0]
        overflow = count - cache_settings.max_entries
        if overflow > 0:
            evicted = db.execute(
                """select e.id,e.normalized,r.scope_id from cache_entries e
                   left join cache_entry_runtime r on r.entry_id=e.id
                   order by coalesce(r.last_accessed_at,e.created_at) asc, e.id asc limit ?""",
                (overflow,),
            ).fetchall()
            for row in evicted:
                hot.delete(row["scope_id"], row["normalized"])
                db.execute("delete from cache_entries where id = ?", (row["id"],))
            if evicted:
                db.executemany("delete from cache_entry_runtime where entry_id = ?", [(row["id"],) for row in evicted])


def _record_lookup(match_type: str, scope_id: str) -> None:
    settings = get_settings()
    with sqlite3.connect(settings.database_path) as db:
        db.execute(
            "insert into cache_lookup_events(created_at, match_type, scope_id) values (?, ?, ?)",
            (_now().isoformat(), match_type, scope_id),
        )


def _touch_entry(entry_id: int, scope_id: str) -> None:
    settings = get_settings()
    with sqlite3.connect(settings.database_path) as db:
        db.execute(
            """update cache_entry_runtime set last_accessed_at=?, hit_count=hit_count+1
               where entry_id=? and scope_id=?""",
            (_now().isoformat(), entry_id, scope_id),
        )


def _semantic_text(text: str) -> str:
    words = normalize(text).split()
    return " ".join(_HINGLISH_EQUIVALENTS.get(word, word) for word in words if _HINGLISH_EQUIVALENTS.get(word, word))


def _nearest(text: str, entries: list[dict]) -> tuple[dict | None, float]:
    if not entries:
        return None, 0.0

    query_vector = _embedder.embed([_semantic_text(text)])[0]
    vectors: list[list[float]] = []
    missing: list[tuple[int, list[float]]] = []
    for index, item in enumerate(entries):
        vector = item.get("embedding")
        if not vector:
            vector = _embedder.embed([_semantic_text(item["question"])])[0].tolist()
            missing.append((int(item["id"]), vector))
        vectors.append(vector)

    if missing:
        settings = get_settings()
        with sqlite3.connect(settings.database_path) as db:
            db.executemany(
                "update cache_entries set embedding_json=? where id=?",
                [(json.dumps(vector), entry_id) for entry_id, vector in missing],
            )

    scores = np.clip(np.asarray(vectors, dtype=np.float64) @ query_vector, 0.0, 1.0)
    best_index = int(np.argmax(scores))
    return entries[best_index], float(scores[best_index])


def _cache_result(item: dict, match_type: str, similarity: float, threshold: float | None = None) -> dict:
    result = {
        "hit": True,
        "match_type": match_type,
        "similarity": round(similarity, 4),
        "matched_question": item["question"],
        "answer": item["answer"],
        "source": item["source"],
        "cache_id": item["id"],
        "note": "Exact match after case, punctuation and whitespace normalization." if match_type == "exact" else "Near-match: review the matched question and similarity before reusing this answer.",
    }
    if threshold is not None:
        result["threshold"] = threshold
    return result


def _lookup(text: str, language: str = "auto", scope_id: str = "public") -> dict:
    scope_id = _validated_scope(scope_id)
    store = _cache_store()
    key = normalize(text)
    if not key:
        raise HTTPException(status_code=422, detail="Question must contain letters or numbers.")

    cache_settings = get_cache_settings()
    hot = _hot_index(cache_settings)
    hot_result = hot.get(scope_id, key)
    if hot_result and isinstance(hot_result.get("cache_id"), int):
        _touch_entry(hot_result["cache_id"], scope_id)
        _record_lookup("exact", scope_id)
        return hot_result

    entries = _entries_for_scope(store, scope_id)
    for item in entries:
        if item["normalized"] == key:
            _touch_entry(item["id"], scope_id)
            result = _cache_result(item, "exact", 1.0)
            hot.set(scope_id, key, result, cache_settings.ttl_seconds)
            _record_lookup("exact", scope_id)
            return result

    best, best_score = _nearest(text, entries)

    threshold = get_cache_settings().semantic_threshold
    if best is not None and best_score >= threshold:
        _touch_entry(best["id"], scope_id)
        _record_lookup("semantic", scope_id)
        return _cache_result(best, "semantic", best_score, threshold)

    _record_lookup("miss", scope_id)
    return {
        "hit": False,
        "match_type": "none",
        "similarity": round(best_score, 4),
        "matched_question": best["question"] if best else None,
        "answer": None,
        "source": best["source"] if best else None,
        "cache_id": best["id"] if best else None,
        "threshold": threshold,
        "note": "No safe cache match. The closest question is shown for review only.",
    }


def _private_content(text: str) -> bool:
    if _EMAIL_RE.search(text) or _URL_RE.search(text) or _ID_RE.search(text) or _PRIVATE_CONTEXT_RE.search(text):
        return True
    digits = re.sub(r"\D", "", text)
    return len(digits) >= 10


def _add_cache_entry(
    question: str,
    answer: str,
    language: str,
    source: str,
    ttl_seconds: int | None,
    scope_id: str,
) -> int:
    store = _cache_store()
    normalized = normalize(question)
    existing = next((item for item in _entries_for_scope(store, scope_id) if item["normalized"] == normalized), None)
    if existing:
        return int(existing["id"])

    embedding = _embedder.embed([_semantic_text(question)])[0].tolist()
    entry_id = store.put_cache(question.strip(), normalized, answer.strip(), language, source, embedding)
    created_at = _now()
    expires_at = (created_at + timedelta(seconds=ttl_seconds)).isoformat() if ttl_seconds else None
    try:
        with store.connect() as db:
            db.execute(
                """insert into cache_entry_runtime(entry_id,last_accessed_at,hit_count,expires_at,scope_id,normalized)
                   values (?,?,0,?,?,?)
                   on conflict(entry_id) do update set last_accessed_at=excluded.last_accessed_at,
                     expires_at=excluded.expires_at,scope_id=excluded.scope_id,normalized=excluded.normalized""",
                (entry_id, created_at.isoformat(), expires_at, scope_id, normalized),
            )
    except sqlite3.IntegrityError:
        # Another request inserted the same normalized question in this scope.
        with store.connect() as db:
            db.execute("delete from cache_entries where id = ?", (entry_id,))
            existing = db.execute(
                "select entry_id from cache_entry_runtime where scope_id=? and normalized=?",
                (scope_id, normalized),
            ).fetchone()
        if existing:
            return int(existing["entry_id"])
        raise
    result = {
        "hit": True,
        "match_type": "exact",
        "similarity": 1.0,
        "matched_question": question.strip(),
        "answer": answer.strip(),
        "source": source,
        "cache_id": entry_id,
        "note": "Exact match after case, punctuation and whitespace normalization.",
    }
    _hot_index().set(scope_id, normalized, result, ttl_seconds or get_cache_settings().ttl_seconds)
    _maintain_cache(store, get_cache_settings())
    return entry_id


@router.post("/lookup")
def lookup(request: CacheLookup, cache_scope: str = Header(default="public", alias="X-Cache-Scope")):
    return _lookup(request.text, request.language, cache_scope)


@router.post("/answer")
async def answer(
    request: CacheAnswerRequest,
    cache_scope: str = Header(default="public", alias="X-Cache-Scope"),
):
    """Cache-aside flow: look up, generate on a miss, then learn reusable answers."""
    cache_scope = _validated_scope(cache_scope)
    key = normalize(request.text)
    if not key:
        raise HTTPException(status_code=422, detail="Question must contain letters or numbers.")

    cached = _lookup(request.text, request.language, cache_scope) if request.use_cache else None
    if cached and cached["hit"]:
        return {
            "answer": cached["answer"],
            "answer_source": "cache",
            "mode": get_settings().mode,
            "cache": {"status": "hit", **cached, "stored": False},
        }

    settings = get_settings()
    generation = await Provider(settings).generate(request.text, settings.cheap_model)
    if not generation.text.strip():
        raise HTTPException(status_code=502, detail="The configured answer provider returned an empty response.")

    cache_settings = get_cache_settings()
    private = _private_content(request.text) or _private_content(generation.text)
    is_fixture = generation.mode == "demo" and generation.source != "fallback"
    should_store = request.store_answer and not private and (generation.mode == "live" or is_fixture)
    source = "live-provider" if generation.mode == "live" else "authored-demo"
    cache_id = None
    if should_store:
        cache_id = _add_cache_entry(
            request.text,
            generation.text,
            request.language,
            source,
            cache_settings.ttl_seconds,
            cache_scope,
        )

    if not request.store_answer:
        store_reason = "saving disabled by request"
    elif private:
        store_reason = "prompt or answer contains a private identifier, contact detail, URL, or secret marker"
    elif not is_fixture and generation.mode != "live":
        store_reason = "generic demo fallback is not reusable content"
    else:
        store_reason = "saved for future exact or similar questions"

    return {
        "answer": generation.text,
        "answer_source": generation.source,
        "mode": generation.mode,
        "model": generation.model,
        "usage": {
            "prompt_tokens": generation.prompt_tokens,
            "completion_tokens": generation.completion_tokens,
            "total_tokens": generation.total_tokens,
        },
        "cache": {
            "status": "miss" if request.use_cache else "bypassed",
            "match_type": "none",
            "similarity": cached["similarity"] if cached else 0.0,
            "matched_question": cached["matched_question"] if cached else None,
            "threshold": cached["threshold"] if cached else cache_settings.semantic_threshold,
            "stored": should_store,
            "cache_id": cache_id,
            "store_reason": store_reason,
            "ttl_seconds": cache_settings.ttl_seconds if should_store else None,
            "durable_backend": "sqlite",
            "redis_status": _hot_index(cache_settings).status(),
        },
    }


@router.get("/entries")
def entries(cache_scope: str = Header(default="public", alias="X-Cache-Scope")):
    cache_scope = _validated_scope(cache_scope)
    settings = get_cache_settings()
    items = _entries_for_scope(_cache_store(), cache_scope)
    return {"items": items, "durable_backend": "sqlite", "redis_status": _hot_index(settings).status()}


@router.post("/entries", status_code=201)
def add_entry(request: CacheEntryInput, cache_scope: str = Header(default="public", alias="X-Cache-Scope")):
    cache_scope = _validated_scope(cache_scope)
    normalized = normalize(request.question)
    if not normalized or not request.answer.strip():
        raise HTTPException(status_code=422, detail="Question and answer must contain text.")
    store = _cache_store()
    existing = next((item for item in _entries_for_scope(store, cache_scope) if item["normalized"] == normalized), None)
    if existing:
        raise HTTPException(status_code=409, detail="An entry with this normalized question already exists.")
    item_id = _add_cache_entry(request.question, request.answer, request.language, "authored", None, cache_scope)
    return {"id": item_id, "question": request.question.strip(), "answer": request.answer.strip(), "language": request.language, "source": "authored"}


@router.post("/seed")
def seed_demo_faqs(cache_scope: str = Header(default="public", alias="X-Cache-Scope")):
    cache_scope = _validated_scope(cache_scope)
    store = _cache_store()
    existing = {item["normalized"] for item in _entries_for_scope(store, cache_scope)}
    added = 0
    for faq in DEMO_FAQS:
        normalized = normalize(faq["question"])
        if normalized not in existing:
            _add_cache_entry(faq["question"], faq["answer"], faq["language"], "authored-demo", None, cache_scope)
            existing.add(normalized)
            added += 1
    return {"added": added, "total": len(_entries_for_scope(store, cache_scope)), "source": "authored-demo"}


@router.delete("/entries/{entry_id}")
def delete_entry(entry_id: int, cache_scope: str = Header(default="public", alias="X-Cache-Scope")):
    cache_scope = _validated_scope(cache_scope)
    settings = get_settings()
    with sqlite3.connect(settings.database_path) as db:
        row = db.execute(
            "select e.normalized from cache_entries e join cache_entry_runtime r on r.entry_id=e.id where e.id = ? and r.scope_id = ?",
            (entry_id, cache_scope),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Cache entry not found.")
        db.execute("delete from cache_entries where id = ?", (entry_id,))
        db.execute("delete from cache_entry_runtime where entry_id = ?", (entry_id,))
    _hot_index().delete(cache_scope, row[0])
    return {"deleted": entry_id}


@router.delete("/entries")
def clear_entries(cache_scope: str = Header(default="public", alias="X-Cache-Scope")):
    cache_scope = _validated_scope(cache_scope)
    settings = get_settings()
    with sqlite3.connect(settings.database_path) as db:
        rows = db.execute(
            "select e.id,e.normalized from cache_entries e join cache_entry_runtime r on r.entry_id=e.id where r.scope_id = ?",
            (cache_scope,),
        ).fetchall()
        if rows:
            placeholders = ",".join("?" for _ in rows)
            ids = [row[0] for row in rows]
            db.execute(f"delete from cache_entries where id in ({placeholders})", ids)
            db.execute(f"delete from cache_entry_runtime where entry_id in ({placeholders})", ids)
    hot = _hot_index()
    for row in rows:
        hot.delete(cache_scope, row[1])
    return {"deleted": len(rows)}


@router.get("/stats")
def stats(cache_scope: str = Header(default="public", alias="X-Cache-Scope")):
    cache_scope = _validated_scope(cache_scope)
    store = _cache_store()
    with store.connect() as db:
        rows = db.execute(
            "select match_type, count(*) as count from cache_lookup_events where scope_id = ? group by match_type",
            (cache_scope,),
        ).fetchall()
        entry_count = db.execute("select count(*) from cache_entry_runtime where scope_id = ?", (cache_scope,)).fetchone()[0]
    counts = {row["match_type"]: row["count"] for row in rows}
    exact = counts.get("exact", 0)
    semantic = counts.get("semantic", 0)
    misses = counts.get("miss", 0)
    return {
        "total_lookups": exact + semantic + misses,
        "exact_hits": exact,
        "semantic_hits": semantic,
        "misses": misses,
        "entries": entry_count,
        "durable_backend": "sqlite",
        "redis_status": _hot_index().status(),
    }
