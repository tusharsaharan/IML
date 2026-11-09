"""CRF sequence tagger for Hinglish Keep/Drop decisions (Stage 4).

Feature set per token: normalized form, phonetic hash, morphology
(suffix/prefix), character-bigram cues (has_rh/has_nh), positional signals,
TF-IDF information content, and a ±2 neighbor window. Protected tokens
(negation/question) and [[PSi]] markers are force-kept in post-processing,
regardless of the model's output.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from gateway.modules.m2_compressor.phonetic import (
    hinglish_phash,
    is_marker,
    is_protected,
    normalize_chars,
)
from gateway.modules.m2_compressor.tfidf import get_tfidf_score

_DEVANAGARI = re.compile(r"[\u0900-\u097F]")
_MIN_KEEP_FRACTION = 0.30


def extract_features(
    tokens: list[str],
    i: int,
    idf_map: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Feature vector for token i with a ±2 neighbor window."""
    tok = tokens[i]
    norm = normalize_chars(tok)
    phash = hinglish_phash(tok)
    tfidf = get_tfidf_score(norm, idf_map)
    n = len(tokens)

    feats: dict[str, Any] = {
        "bias": 1.0,
        "token.lower": norm,
        "token.phash": phash,
        "token.len": len(tok),
        "token.is_short": len(tok) <= 2,
        "token.is_alpha": tok.isalpha(),
        "token.is_ascii": tok.isascii(),
        "token.has_devanagari": bool(_DEVANAGARI.search(tok)),
        "token.is_marker": is_marker(tok),
        "token.is_protected": is_protected(norm),
        "token.suffix1": norm[-1:],
        "token.suffix2": norm[-2:],
        "token.suffix3": norm[-3:],
        "token.prefix1": norm[:1],
        "token.prefix2": norm[:2],
        "token.prefix3": norm[:3],
        "token.has_rh": ("rh" in norm) or phash.startswith("RH"),
        "token.has_nh": ("nh" in norm) or phash == "NH",
        "token.ends_vowel": (norm[-1:] in "aeiou") if norm else False,
        "token.is_first": i == 0,
        "token.is_last": i == n - 1,
        "token.is_second": i == 1,
        "token.is_penult": i == n - 2,
        "token.position_ratio": round(i / max(1, n - 1), 4),
        "token.tfidf_score": round(tfidf, 4),
        "token.is_high_freq": tfidf > 0.8,
        "token.is_low_freq": tfidf < 0.2,
    }

    for offset in (-2, -1, 1, 2):
        j = i + offset
        prefix = f"{offset:+d}"
        if 0 <= j < n:
            ntok = tokens[j]
            nnorm = normalize_chars(ntok)
            feats[f"{prefix}.lower"] = nnorm
            feats[f"{prefix}.phash"] = hinglish_phash(ntok)
            feats[f"{prefix}.suffix2"] = nnorm[-2:]
            feats[f"{prefix}.is_marker"] = is_marker(ntok)
            feats[f"{prefix}.is_protected"] = is_protected(nnorm)
        else:
            feats[f"{prefix}.BOS"] = j < 0
            feats[f"{prefix}.EOS"] = j >= n
    return feats


def featurize(
    tokens: list[str], idf_map: dict[str, float] | None = None
) -> list[dict[str, Any]]:
    return [extract_features(tokens, i, idf_map) for i in range(len(tokens))]


def apply_safety_gates(tokens: list[str], labels: list[str]) -> list[str]:
    """Force-keep protected tokens + markers; enforce minimum-keep floor."""
    fixed = list(labels)
    for i, tok in enumerate(tokens):
        if is_marker(tok) or is_protected(normalize_chars(tok)):
            fixed[i] = "K"
    kept = sum(1 for lab in fixed if lab == "K")
    floor = max(2, int(_MIN_KEEP_FRACTION * len(tokens)))
    if kept < floor:
        fixed = ["K"] * len(tokens)
    return fixed


def is_available() -> bool:
    """True when sklearn-crfsuite is importable (pip install -e '.[crf]')."""
    try:
        import sklearn_crfsuite  # noqa: F401

        return True
    except Exception:
        return False


class CRFTagger:
    """Thin wrapper: lazy pickle load, featurize -> predict -> safety gates."""

    def __init__(
        self,
        model_path: Path | str | None = None,
        idf_map: dict[str, float] | None = None,
    ) -> None:
        self.model_path = Path(model_path) if model_path else None
        self.idf_map = idf_map or {}
        self._model = None

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def _ensure(self):
        if self._model is None:
            if not is_available():
                raise ImportError("sklearn-crfsuite not installed (pip install -e '.[crf]')")
            if self.model_path is None or not self.model_path.exists():
                raise FileNotFoundError(f"CRF model not found: {self.model_path}")
            import pickle

            with self.model_path.open("rb") as fh:
                self._model = pickle.load(fh)
        return self._model

    def predict(self, tokens: list[str]) -> list[str]:
        if not tokens:
            return []
        model = self._ensure()
        feats = featurize(tokens, self.idf_map)
        raw = model.predict_single(feats)
        labels = [str(lab) for lab in raw]
        return apply_safety_gates(tokens, labels)
