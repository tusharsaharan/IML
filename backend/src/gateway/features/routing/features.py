"""Pure, deterministic feature extraction for the routing feature.

Nothing here calls a provider, loads a model or uses randomness. Labels used
later by the classifiers are authored fixtures, not measured model correctness.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from gateway.modules.m1_pipeline.hinglish import (
    code_mix_detail,
    code_mix_ratio,
    language_group,
)
from gateway.modules.m4_router.difficulty import DifficultyScorer
from gateway.tokenizer import TokenCounter

# Longer prompts are truncated before extraction; `truncated` records that.
MAX_CHARS = 20_000

# Numeric model inputs, in fixed order. Every value is safe to feed to sklearn.
MODEL_FEATURE_NAMES: tuple[str, ...] = (
    "char_length",
    "word_count",
    "devanagari_ratio",
    "latin_ratio",
    "code_mix_ratio",
    "roman_hindi_ratio",
    "lang_english",
    "lang_hinglish",
    "lang_mixed_script",
    "lang_hindi",
    "difficulty_entity_density",
    "difficulty_math_marker_count",
    "has_digits",
    "has_math_symbols",
    "has_code_markers",
    "has_email_or_amount",
)

# Display/audit only; deliberately excluded from MODEL_FEATURE_NAMES.
DISPLAY_FEATURE_NAMES: tuple[str, ...] = (
    "language_group",
    "reference_token_count",
    "tokenizer_backend",
    "truncated",
)

_DEVANAGARI = re.compile(r"[\u0900-\u097f]")
_MATH_SYMBOLS = re.compile(r"[+\-*/=<>^%]")
_CODE_MARKERS = re.compile(r"`|\bdef\s|\{|=>")
_EMAIL_OR_AMOUNT = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}" r"|(?:rs\.?|inr|₹|\$)\s?\d",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class RoutingFeatures:
    """Extracted routing features.

    Model values follow MODEL_FEATURE_NAMES. `word_count` counts whitespace
    words, not tokenizer tokens. `reference_token_count` is a reference count
    from `TokenCounter`, never provider billing, and is excluded from the model
    because it changes under the whitespace fallback when tiktoken is missing.

    language_group rule: `devanagari_ratio >= 0.8` -> "hindi"; no letters at
    all -> "unknown"; otherwise the imported `hinglish.language_group` value
    (english | hinglish | mixed_script). That imported helper has no pure-Hindi
    group, which is why the Devanagari-share rule is applied first.
    """

    char_length: int
    word_count: int
    devanagari_ratio: float
    latin_ratio: float
    code_mix_ratio: float
    roman_hindi_ratio: float
    lang_english: int
    lang_hinglish: int
    lang_mixed_script: int
    lang_hindi: int
    difficulty_entity_density: float
    difficulty_math_marker_count: int
    has_digits: int
    has_math_symbols: int
    has_code_markers: int
    has_email_or_amount: int
    language_group: str
    reference_token_count: int
    tokenizer_backend: str
    truncated: bool

    def vector(self) -> list[float]:
        """Model inputs as floats, in MODEL_FEATURE_NAMES order."""
        return [float(getattr(self, name)) for name in MODEL_FEATURE_NAMES]

    def as_dict(self) -> dict[str, float | int | str | bool]:
        """Every feature, model and display-only, JSON-serializable."""
        return {
            name: getattr(self, name)
            for name in (*MODEL_FEATURE_NAMES, *DISPLAY_FEATURE_NAMES)
        }


@lru_cache(maxsize=1)
def _counter() -> TokenCounter:
    return TokenCounter()


@lru_cache(maxsize=1)
def _difficulty() -> DifficultyScorer:
    return DifficultyScorer()


def _letter_ratios(text: str) -> tuple[float, float, int]:
    """Devanagari and ASCII-Latin share of all Unicode letters in `text`."""
    devanagari = latin = total = 0
    for char in text:
        if char.isalpha():
            total += 1
            if _DEVANAGARI.match(char):
                devanagari += 1
            elif char.isascii():
                latin += 1
    if total == 0:
        return 0.0, 0.0, 0
    return round(devanagari / total, 6), round(latin / total, 6), total


def extract_features(text: str) -> RoutingFeatures:
    """Extract routing features from at most the first MAX_CHARS characters.

    `char_length` is the full input length; every other value describes the
    processed prefix. Never raises for empty, whitespace, emoji or long input.
    """
    sample = text[:MAX_CHARS]
    truncated = len(text) > MAX_CHARS
    devanagari_ratio, latin_ratio, letter_total = _letter_ratios(sample)
    detail = code_mix_detail(sample)
    group = _language_group(sample, devanagari_ratio, letter_total)
    difficulty = _difficulty().features(sample)
    counter = _counter()
    return RoutingFeatures(
        char_length=len(text),
        word_count=len(sample.split()),
        devanagari_ratio=devanagari_ratio,
        latin_ratio=latin_ratio,
        code_mix_ratio=code_mix_ratio(sample),
        roman_hindi_ratio=(
            round(detail["roman_hindi"] / detail["n"], 6) if detail["n"] else 0.0
        ),
        lang_english=int(group == "english"),
        lang_hinglish=int(group == "hinglish"),
        lang_mixed_script=int(group == "mixed_script"),
        lang_hindi=int(group == "hindi"),
        difficulty_entity_density=difficulty.entity_density,
        difficulty_math_marker_count=difficulty.math_marker_count,
        has_digits=int(any(char.isdigit() for char in sample)),
        has_math_symbols=int(bool(_MATH_SYMBOLS.search(sample))),
        has_code_markers=int(bool(_CODE_MARKERS.search(sample))),
        has_email_or_amount=int(bool(_EMAIL_OR_AMOUNT.search(sample))),
        language_group=group,
        reference_token_count=counter.count(sample),
        tokenizer_backend=counter.backend,
        truncated=truncated,
    )


def _language_group(text: str, devanagari_ratio: float, letter_total: int) -> str:
    if letter_total == 0:
        return "unknown"
    if devanagari_ratio >= 0.8:
        return "hindi"
    return language_group(text)
