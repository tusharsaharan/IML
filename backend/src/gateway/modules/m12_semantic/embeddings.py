from __future__ import annotations

import hashlib
import re
import unicodedata
from functools import lru_cache

import numpy as np

# Word tokens: roman a-z0-9 + Devanagari block. Punctuation is dropped so
# "refund?" and "refund" hash identically; entities (emails/phones) still
# contribute shared character n-grams below.
_WORD = re.compile(r"[a-z0-9\u0900-\u097f]+")

#: Default multilingual checkpoint used when the `semantic` extra is
#: installed (`pip install -e ".[semantic]"`). Small (~120MB), CPU-runnable,
#: covers 50+ languages incl. Hindi (roman + Devanagari).
DEFAULT_ST_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

#: Fallback vector width for the offline hash embedder.
HASH_DIM = 512

#: Meaning-preserved threshold for the *hash* backend, calibrated on the
#: seed set (identical=1.0, filler-drop≈0.9, unrelated≈0.1–0.3).
#: ST-backend users should raise this to ~0.75 (tighter cross-lingual space).
HASH_THRESHOLD = 0.55


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    return re.sub(r"\s+", " ", text).strip()


def _hash_index(token: str, dim: int) -> int:
    return int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % dim


def _hash_embed(texts: list[str], dim: int = HASH_DIM) -> np.ndarray:
    """Deterministic offline vectors: word unigrams (w=2) + char trigrams (w=1).

    Char trigrams give transliteration robustness (nahi/nahin share most
    trigrams); word weights keep exact content words dominant. No fitted
    state, no downloads, no extra dependencies beyond numpy.
    """
    mat = np.zeros((len(texts), dim), dtype=np.float64)
    for i, raw in enumerate(texts):
        t = _norm(raw)
        if not t:
            continue
        for w in _WORD.findall(t):
            mat[i, _hash_index("w:" + w, dim)] += 2.0
        spaceless = t.replace(" ", "")
        for j in range(max(0, len(spaceless) - 2)):
            mat[i, _hash_index("c:" + spaceless[j : j + 3], dim)] += 1.0
        n = float(np.linalg.norm(mat[i]))
        if n > 0:
            mat[i] /= n
    return mat


class SemanticEmbedder:
    """Multilingual sentence vectors with an offline hash fallback.

    Backend is ``"st"`` when sentence-transformers loads a model,
    else ``"hash"``. Both return L2-normalized rows so cosine == dot.
    Follows the repo pattern (TokenCounter whitespace fallback,
    MockLLMClient dry-run): never raise for missing optionals.
    """

    def __init__(self, model_name: str = DEFAULT_ST_MODEL, dim: int = HASH_DIM, use_st: bool = True) -> None:
        self.dim = dim
        self.model_name = model_name
        self.backend = "hash"
        self._st = None
        if use_st:
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore

                self._st = SentenceTransformer(model_name)
                self.backend = "st"
            except Exception:
                self._st = None
                self.backend = "hash"

    def embed(self, texts: list[str]) -> np.ndarray:
        if self._st is not None:
            try:
                vecs = self._st.encode(texts, normalize_embeddings=True, show_progress_bar=False)
                return np.asarray(vecs, dtype=np.float64)
            except Exception:
                self._st = None
                self.backend = "hash"
        return _hash_embed(texts, self.dim)

    def similarity(self, a: str, b: str) -> float:
        if not (a or "").strip() or not (b or "").strip():
            return 0.0
        m = self.embed([a, b])
        return round(float(np.clip(float(m[0] @ m[1]), 0.0, 1.0)), 6)

    def meaning_preserved(self, original: str, compressed: str, threshold: float = HASH_THRESHOLD) -> tuple[float, bool]:
        sim = self.similarity(original, compressed)
        return sim, sim >= threshold

    def nearest(self, query: str, candidates: list[str], threshold: float = HASH_THRESHOLD) -> tuple[str | None, float]:
        """Nearest candidate above threshold — the semantic-cache lookup primitive."""
        if not candidates or not query.strip():
            return None, 0.0
        m = self.embed([query, *candidates])
        q = m[0]
        best, best_s = None, 0.0
        for cand, v in zip(candidates, m[1:]):
            s = float(np.clip(float(q @ v), 0.0, 1.0))
            if s > best_s:
                best, best_s = cand, s
        if best is not None and best_s >= threshold:
            return best, round(best_s, 6)
        return None, round(best_s, 6)


@lru_cache(maxsize=1)
def get_embedder() -> SemanticEmbedder:
    return SemanticEmbedder()


def semantic_similarity(a: str, b: str) -> float:
    return get_embedder().similarity(a, b)
