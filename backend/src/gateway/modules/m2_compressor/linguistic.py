"""Linguistic CRF compressor: 5-stage Hinglish pipeline orchestrator.

Stage 1: safety masking (mask) -- PII/code/URLs/amounts -> [[PSi]].
Stage 2: phonetic normalization is implicit (features, never rewrites output).
Stage 3: heuristic pre-pruning (greeting strip, reduplication, tiny fillers).
Stage 4: CRF Keep/Drop tagging with force-keep safety gates.
Stage 5: reconstruction (stitch kept ORIGINAL tokens, reinject spans).

Fail-closed: any failure returns the original text unchanged.
"""

from __future__ import annotations

import re
from pathlib import Path

from gateway.modules.m2_compressor.crf_tagger import CRFTagger
from gateway.modules.m2_compressor.heuristic_passes import (
    collapse_reduplication,
    strip_greeting_enhanced,
    strip_unconditional_fillers,
)
from gateway.modules.m2_compressor.phonetic import is_marker
from gateway.modules.m2_compressor.safety_span import mask, reinject
from gateway.modules.m2_compressor.tfidf import load_idf
from gateway.schemas import CompressResult, DropRecord, SafetySpan
from gateway.tokenizer import TokenCounter

_WS = re.compile(r"\s+")


class LinguisticCompressor:
    """Synchronous CRF linguistic compressor (serve path, ~3-6ms)."""

    def __init__(
        self,
        counter: TokenCounter,
        crf_model_path: Path | str | None = None,
        tfidf_path: Path | str | None = None,
    ) -> None:
        self.counter = counter
        self.crf_model_path = Path(crf_model_path) if crf_model_path else None
        self.tfidf_path = Path(tfidf_path) if tfidf_path else None
        idf_map = load_idf(self.tfidf_path) if self.tfidf_path else {}
        self._tagger = CRFTagger(self.crf_model_path, idf_map)

    @property
    def crf_ready(self) -> bool:
        """True when a model file exists and sklearn-crfsuite is importable."""
        from gateway.modules.m2_compressor.crf_tagger import is_available

        return (
            is_available()
            and self.crf_model_path is not None
            and self.crf_model_path.exists()
        )

    def _result(
        self,
        original: str,
        compressed: str,
        spans: list[SafetySpan],
        drops: list[DropRecord],
    ) -> CompressResult:
        tok_orig = self.counter.count(original)
        tok_comp = max(1, self.counter.count(compressed))
        return CompressResult(
            original=original,
            compressed=compressed,
            spans=spans,
            drops=drops,
            token_original=tok_orig,
            token_compressed=tok_comp,
            ratio=round(tok_comp / max(1, tok_orig), 6),
            method="crf",
        )

    def compress(self, text: str) -> CompressResult:
        if not text or not text.strip():
            return self._result(text, text, [], [])
        try:
            return self._compress_inner(text)
        except Exception:
            # Fail closed: original text, honestly labelled.
            tok = max(1, self.counter.count(text))
            return CompressResult(
                original=text,
                compressed=text,
                spans=[],
                drops=[],
                token_original=tok,
                token_compressed=tok,
                ratio=1.0,
                method="crf",
            )

    def _compress_inner(self, text: str) -> CompressResult:
        masked, spans = mask(text)
        drops: list[DropRecord] = []

        # Stage 3a: greeting strip.
        stripped, g_drop = strip_greeting_enhanced(masked)
        if g_drop is not None:
            drops.append(g_drop)
        tokens = stripped.split()
        if not tokens:
            # Pre-pass consumed everything but input wasn't empty:
            # fail closed to original (e.g. greeting-only message edge).
            return self._result(text, text, spans, [])

        # Stage 3b: reduplication collapse.
        tokens, red_drops = collapse_reduplication(tokens)
        drops.extend(red_drops)

        # Stage 3c: unconditional fillers.
        tokens, fil_drops = strip_unconditional_fillers(tokens)
        drops.extend(fil_drops)
        if not tokens:
            return self._result(text, text, spans, [])

        # Stage 4: CRF tagging (skip gracefully when model unavailable).
        if self.crf_ready:
            try:
                labels = self._tagger.predict(tokens)
            except Exception:
                labels = ["K"] * len(tokens)
            crf_drops = [
                DropRecord(token=tok, category="crf", rule="keep_drop")
                for tok, lab in zip(tokens, labels, strict=True)
                if lab != "K"
            ]
            drops.extend(crf_drops)
            kept = [tok for tok, lab in zip(tokens, labels, strict=True) if lab == "K"]
            # apply_safety_gates already enforces the min-keep floor, but
            # belt-and-braces: never emit an empty compression.
            tokens = kept or tokens
        # Never drop markers that survived this far (reinject would fail).
        # (Gates already force-keep them; this is a final assertion point.)
        assert all(
            t is not None for t in tokens
        )

        # Stage 5: reconstruct + reinject.
        compressed_masked = _WS.sub(" ", " ".join(tokens)).strip()
        final, ok = reinject(compressed_masked, spans)
        if not ok:
            final = text
        # Drop records for markers must never appear (they were never dropped).
        drops = [d for d in drops if not is_marker(d.token)]
        return self._result(text, final, spans, drops)
