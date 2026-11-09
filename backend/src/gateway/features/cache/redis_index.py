from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from typing import Any


@lru_cache(maxsize=2)
def _client(url: str):
    from redis import Redis  # type: ignore[import-not-found]

    return Redis.from_url(url, decode_responses=True, socket_connect_timeout=0.2, socket_timeout=0.2)


class RedisExactIndex:
    """Optional Redis/Valkey exact-answer hot index; SQLite remains authoritative."""

    def __init__(self, url: str):
        self.url = url.strip()
        self._unavailable = False

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    def _key(self, scope: str, normalized_question: str) -> str:
        digest = hashlib.sha256(f"{scope}\0{normalized_question}".encode("utf-8")).hexdigest()
        return f"iml:cache:exact:v1:{digest}"

    def get(self, scope: str, normalized_question: str) -> dict[str, Any] | None:
        if not self.enabled or self._unavailable:
            return None
        try:
            value = _client(self.url).get(self._key(scope, normalized_question))
            return json.loads(value) if value else None
        except Exception:
            self._unavailable = True
            return None

    def set(self, scope: str, normalized_question: str, value: dict[str, Any], ttl_seconds: int) -> None:
        if not self.enabled or self._unavailable:
            return
        try:
            client = _client(self.url)
            payload = json.dumps(value, ensure_ascii=False)
            if ttl_seconds > 0:
                client.set(self._key(scope, normalized_question), payload, ex=ttl_seconds)
            else:
                client.set(self._key(scope, normalized_question), payload)
        except Exception:
            self._unavailable = True

    def delete(self, scope: str, normalized_question: str) -> None:
        if not self.enabled or self._unavailable:
            return
        try:
            _client(self.url).delete(self._key(scope, normalized_question))
        except Exception:
            self._unavailable = True

    def status(self) -> str:
        if not self.enabled:
            return "disabled"
        if self._unavailable:
            return "unavailable; using SQLite"
        try:
            _client(self.url).ping()
            return "connected"
        except Exception:
            self._unavailable = True
            return "unavailable; using SQLite"
