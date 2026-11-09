"""TF-IDF information-content scores for Hinglish tokens.

A static, pre-computed token -> [0,1] map built offline from a Hinglish
corpus (see scripts/build_tfidf.py). High score = rare/informative (keep);
low score = common/redundant (drop candidate). This is a *feature* for the
CRF, never a standalone decision maker.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path

_DEFAULT_OOV = 0.5


@functools.lru_cache(maxsize=4)
def _load_map(path_str: str) -> dict[str, float]:
    try:
        data = json.loads(Path(path_str).read_text(encoding="utf-8"))
        return {str(k): float(v) for k, v in data.items()}
    except Exception:
        return {}


def load_idf(path: Path | str | None) -> dict[str, float]:
    """Load the IDF map (cached). Empty dict when path is missing/corrupt."""
    if path is None:
        return {}
    return _load_map(str(path))


def get_tfidf_score(norm_token: str, idf_map: dict[str, float] | None = None) -> float:
    """Score for an already-normalized token; 0.5 default for OOV."""
    if not norm_token:
        return _DEFAULT_OOV
    if not idf_map:
        return _DEFAULT_OOV
    v = idf_map.get(norm_token)
    return float(v) if v is not None else _DEFAULT_OOV
