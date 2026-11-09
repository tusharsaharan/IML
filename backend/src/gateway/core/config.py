from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[4]
DATA = ROOT / "backend" / "data"
RUNTIME = DATA / "runtime"
ARTIFACTS = DATA / "artifacts"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    mode: Literal["demo", "live"] = "demo"
    host: str = "127.0.0.1"
    port: int = 8000
    api_base_url: str = ""
    api_key: str = ""
    cheap_model: str = "demo-cheap"
    strong_model: str = "demo-strong"
    cheap_input_price: float | None = None
    cheap_output_price: float | None = None
    strong_input_price: float | None = None
    strong_output_price: float | None = None
    encoding: str = "cl100k_base"
    cache_threshold: float = 0.88
    database_path: Path = RUNTIME / "iml.sqlite3"


@lru_cache
def get_settings() -> Settings:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    return Settings()
