from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[4]
DATA = ROOT / "backend" / "data"
RUNTIME = DATA / "runtime"
ARTIFACTS = DATA / "artifacts"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", env_file_encoding="utf-8", env_prefix="IML_", extra="ignore"
    )

    mode: Literal["demo", "live"] = "demo"
    host: str = "127.0.0.1"
    port: int = 8000
    api_base_url: str = ""
    api_key: str = ""
    cheap_model: str = "demo-cheap"
    strong_model: str = "demo-strong"
    cheap_input_price: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    cheap_output_price: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    strong_input_price: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    strong_output_price: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    encoding: str = "cl100k_base"
    cache_threshold: float = 0.88
    database_path: Path = RUNTIME / "iml.sqlite3"

    @field_validator("cheap_input_price", "cheap_output_price", "strong_input_price", "strong_output_price", mode="before")
    @classmethod
    def blank_price(cls, value):
        return None if value == "" else value

    @field_validator("cheap_model", "strong_model", mode="before")
    @classmethod
    def demo_model_default(cls, value, info):
        return value or ("demo-cheap" if info.field_name == "cheap_model" else "demo-strong")


@lru_cache
def get_settings() -> Settings:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    return Settings()
