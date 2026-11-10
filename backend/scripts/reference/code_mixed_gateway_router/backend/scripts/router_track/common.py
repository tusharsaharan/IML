"""Shared helpers for the autonomous router-track pipeline (local, free Groq).

All generated artifacts live in backend/data/router_track/ (gitignored).
Groq key is read ONLY from the GROQ_API_KEY env var — never stored in files.
Free-only tier mapping (Sept 2026 Groq lineup, disclosed as proxy):
  cheap   = openai/gpt-oss-20b
  premium = openai/gpt-oss-120b
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parents[2]
DATA = BACKEND / "data"
TRACK = DATA / "router_track"

CHEAP_MODEL = "openai/gpt-oss-20b"
PREMIUM_MODEL = "openai/gpt-oss-120b"
GROQ_BASE = "https://api.groq.com/openai/v1"
SEED = 42


def track() -> Path:
    TRACK.mkdir(parents=True, exist_ok=True)
    return TRACK


def _key_pool() -> list[str]:
    raw = os.environ.get("GROQ_API_KEYS", "") or os.environ.get("GROQ_API_KEY", "")
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    assert keys, "Set GROQ_API_KEYS (comma-separated) or GROQ_API_KEY env var"
    return keys


_KEYS: list[str] | None = None
_KEY_COOLDOWN: dict[str, float] = {}  # key -> unix time when usable again
_KEY_IDX = 0


def _keys() -> list[str]:
    global _KEYS
    if _KEYS is None:
        _KEYS = _key_pool()
    return _KEYS


def _pick_key() -> tuple[str, bool]:
    """Round-robin over keys, skipping cooled-down ones. Returns (key, all_parked)."""
    global _KEY_IDX
    keys = _keys()
    now = time.time()
    for _ in range(len(keys)):
        k = keys[_KEY_IDX % len(keys)]
        _KEY_IDX += 1
        if _KEY_COOLDOWN.get(k, 0) <= now:
            return k, False
    # all parked: wait for the earliest one
    earliest = min(_KEY_COOLDOWN.values())
    wait = max(0.0, earliest - now)
    if wait > 0:
        print(f"  all keys cooling, sleeping {int(wait)}s ...")
        time.sleep(wait)
    return keys[0], True


def _park_key(k: str, secs: float) -> None:
    _KEY_COOLDOWN[k] = time.time() + secs


def groq_key() -> str:
    k, _ = _pick_key()
    return k


def load_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def chat_once(model: str, text: str, max_tokens: int = 256) -> tuple[str, dict]:
    """Single Groq chat call with retry/backoff. Returns (content, usage)."""
    headers = {"Authorization": f"Bearer {groq_key()}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": text[:1500]}],
        "temperature": 0.0,
        "max_tokens": max_tokens,
        # gpt-oss spends most tokens on hidden reasoning; 'low' cuts TPM burn
        # ~5x (62 -> 8 reasoning tokens measured) so free-tier 429s stop.
        "reasoning_effort": "low",
    }
    last_err = ""
    for attempt in range(6):
        key, _ = _pick_key()
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        try:
            with httpx.Client(timeout=60) as client:
                r = client.post(f"{GROQ_BASE}/chat/completions", headers=headers, json=payload)
                if r.status_code == 429:
                    _park_key(key, 120)  # park this key 2 min, fail over to the pool
                    print(f"  429 on key ...{key[-4:]}, parked 2m, failing over ...")
                    continue
                r.raise_for_status()
                j = r.json()
                msg = j["choices"][0]["message"]
                # gpt-oss puts hidden thought in msg['reasoning']; when the model
                # spends its whole budget thinking, content comes back empty.
                content = (msg.get("content") or "").strip()
                if not content:
                    content = (msg.get("reasoning") or "").strip()
                return content, j.get("usage", {})
        except httpx.HTTPStatusError as e:
            last_err = f"HTTP {e.response.status_code}"
            if e.response.status_code == 429:
                _park_key(key, 120)
                continue
            time.sleep(5 * (attempt + 1))
        except Exception as e:  # noqa: BLE001
            last_err = str(e)[:120]
            time.sleep(5 * (attempt + 1))
    return f"[ERROR {last_err}]", {}
