"""Application cache adapter used by core orchestration and management APIs.

The pipeline owns request context and reuse approval. This feature owns storage,
lookup, expiry, scope validation and the existing private-content guard.
"""
import re

from .api import _add_cache_entry, _cache_store, _lookup, _private_content, _validated_scope
from .settings import get_cache_settings


def lookup(text: str, language: str, scope: str) -> dict:
    return _lookup(text, language, _validated_scope(scope))


def reusable(text: str, answer: str) -> bool:
    return not (_private_content(text) or _private_content(answer))


def remember(text: str, answer: str, language: str, source: str, scope: str) -> int | None:
    entry_id = _add_cache_entry(text, answer, language, source, get_cache_settings().ttl_seconds, scope)
    # The existing cache refuses duplicate normalized keys. Changed operators or
    # punctuation can share that key; do not claim the new answer was saved when
    # the existing entry was retained (also covers concurrent insertion).
    with _cache_store().connect() as db:
        row = db.execute("select question,answer from cache_entries where id=?", (entry_id,)).fetchone()
    if row is None or row["answer"] != answer.strip():
        return None
    def canonical(value):
        return re.sub(r"\s+", " ", value).strip().casefold()
    return entry_id if canonical(row["question"]) == canonical(text) else None
