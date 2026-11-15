from __future__ import annotations

import json
from dataclasses import dataclass
from typing import AsyncIterator

import httpx

from .config import ROOT, Settings

FIXTURES = ROOT / "backend" / "data" / "fixtures" / "demo_answers.json"


@dataclass
class Generation:
    text: str
    model: str
    mode: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    source: str = "fixture"


class Provider:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.fixtures = self._load_fixtures()

    def _load_fixtures(self) -> list[dict]:
        if not FIXTURES.exists():
            return []
        try:
            return json.loads(FIXTURES.read_text(encoding="utf-8"))
        except Exception:
            return []

    def is_live(self) -> bool:
        return bool(
            self.settings.mode == "live" and self.settings.api_base_url and self.settings.api_key
            and self.settings.cheap_model and self.settings.strong_model
            and not self.settings.cheap_model.startswith("demo-")
            and not self.settings.strong_model.startswith("demo-")
        )

    def answer_fixture(self, text: str) -> Generation:
        lowered = text.lower()
        for item in self.fixtures:
            if any(token in lowered for token in item.get("match", [])):
                return Generation(text=item["answer"], model=self.settings.cheap_model, mode="demo", source=item.get("id", "fixture"))
        fallback = (
            "I can demonstrate the optimisation pipeline for this request. In live mode, the selected model generates the final answer; "
            "in demo mode, the app uses curated responses for common support examples."
        )
        return Generation(text=fallback, model=self.settings.cheap_model, mode="demo", source="fallback")

    async def generate(self, text: str, model: str, *, max_tokens: int | None = None,
                       format_constraint: str | None = None) -> Generation:
        if not self.is_live():
            out = self.answer_fixture(text)
            out.model = model
            return out
        payload = {"model": model, "messages": [{"role": "user", "content": text}], "temperature": 0.2}
        if format_constraint:
            payload["messages"].insert(0, {"role": "system", "content": f"Answer format: {format_constraint}."})
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                self.settings.api_base_url.rstrip("/") + "/chat/completions",
                headers={"Authorization": f"Bearer {self.settings.api_key}"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        choice = data["choices"][0]["message"]["content"]
        if not isinstance(choice, str) or not choice.strip():
            raise ValueError("Provider returned no answer text.")
        usage = data.get("usage") or {}
        if not isinstance(usage, dict) or any(
            value is not None and (type(value) is not int or value < 0)
            for value in (usage.get(key) for key in ("prompt_tokens", "completion_tokens", "total_tokens"))
        ):
            raise ValueError("Invalid provider usage.")
        return Generation(
            text=choice,
            model=model,
            mode="live",
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            total_tokens=usage.get("total_tokens"),
            source="live",
        )

    async def stream(self, text: str, model: str) -> AsyncIterator[str]:
        result = await self.generate(text, model)
        for chunk in result.text.split():
            yield chunk + " "
