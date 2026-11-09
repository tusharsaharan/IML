from __future__ import annotations

import re

from gateway.modules.m1_pipeline.hinglish import code_mix_ratio
from gateway.schemas import DifficultyFeature
from gateway.tokenizer import TokenCounter

_MATH = re.compile(
    r"(\d+\s*[+\-*/=<>]\s*\d+|solve|integrate|derivative|probability|percentage|numerical|equation|formula)",
    re.IGNORECASE,
)
_ENTITY = re.compile(
    r"(\d+|Rs\.?\s?\d[\d,]*|\+?\d[\d\s-]{7,}\d|https?://\S+|@[A-Za-z0-9._%+-]+)"
)


class DifficultyScorer:
    """Heuristic difficulty proxy combining code-mix ratio, entity density, and math markers."""

    W_CODE_MIX = 0.40
    W_ENTITY = 0.30
    W_MATH = 0.20
    W_LENGTH = 0.10

    def __init__(self, counter: TokenCounter | None = None, max_chars: int = 400) -> None:
        self.counter = counter or TokenCounter()
        self.max_chars = max_chars

    def features(self, text: str) -> DifficultyFeature:
        tokens = text.split()
        n = len(tokens)
        cm = code_mix_ratio(text)
        entity_count = len(_ENTITY.findall(text))
        math_count = len(_MATH.findall(text))
        return DifficultyFeature(
            char_count=len(text),
            token_count=n,
            code_mix_ratio=cm,
            entity_density=round(entity_count / n, 6) if n else 0.0,
            math_marker_count=math_count,
        )

    def score(self, text: str) -> float:
        f = self.features(text)
        length = min(1.0, f.char_count / self.max_chars)
        s = (
            self.W_CODE_MIX * f.code_mix_ratio
            + self.W_ENTITY * f.entity_density
            + self.W_MATH * min(1.0, f.math_marker_count / 3.0)
            + self.W_LENGTH * length
        )
        return round(min(1.0, max(0.0, s)), 6)