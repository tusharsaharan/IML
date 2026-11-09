from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from gateway.core.config import ROOT


class CacheSettings(BaseSettings):
    """Cache-specific controls kept separate from the shared gateway settings."""

    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        env_prefix="IML_CACHE_",
        extra="ignore",
    )

    ttl_seconds: int = Field(default=60 * 60 * 24 * 30, ge=60)
    max_entries: int = Field(default=10_000, ge=100)
    semantic_threshold: float = Field(default=0.55, ge=0.0, le=1.0)
    redis_url: str = ""


@lru_cache(maxsize=1)
def get_cache_settings() -> CacheSettings:
    return CacheSettings()
