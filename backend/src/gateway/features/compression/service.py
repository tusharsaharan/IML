"""Feature adapter for the pinned Research compressor, not a new algorithm."""
from __future__ import annotations

import hashlib
import json
import math
import re
import threading
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from time import perf_counter

from gateway.modules.m2_compressor.compressor import Compressor
from gateway.modules.m2_compressor.crf_tagger import CRFTagger
from gateway.modules.m2_compressor.phonetic import is_protected, normalize_chars
from gateway.modules.m2_compressor.safety_span import detect_spans
from gateway.schemas import CompressResult
from gateway.tokenizer import TokenCounter

ROOT = Path(__file__).resolve().parents[4]
COMMIT = "fa1258135268ca2650170a3f358975ce49169290"
REPOSITORY = "https://github.com/tusharsaharan/Research"

# Verbatim prompts from the pinned upstream regression tests, not benchmarks.
SAMPLES = [
    {"id": "hinglish", "label": "Hinglish email request", "language": "hinglish",
     "text": "yaar matlab mera email user@example.com par bhejo na",
     "source": "backend/tests/test_lexicon.py#test_compressor_drops_audited"},
    {"id": "english", "label": "English filler request", "language": "en",
     "text": "wifi is slow, like really slow, fix it",
     "source": "backend/tests/test_lexicon.py#test_like_comma_hedge_dropped"},
    {"id": "mixed", "label": "Hindi and English", "language": "hi",
     "text": "मेरा wifi काम नहीं कर रहा",
     "source": "backend/tests/test_linguistic_compressor.py#test_devanagari_passthrough"},
]


class ObservedTagger(CRFTagger):
    """Observe execution only; preserve upstream features, predictions and gates."""

    succeeded = False

    def predict(self, tokens: list[str]) -> list[str]:
        labels = super().predict(tokens)
        self.succeeded = True
        return labels


def source_url(source: str) -> str:
    return f"{REPOSITORY}/blob/{COMMIT}/{source}"


def audit_diff(original: str, compressed: str) -> tuple[list[dict], list[dict]]:
    """Token/whitespace diff for display; never used to decide compression."""
    old = list(re.finditer(r"\S+|\s+", original))
    new = list(re.finditer(r"\S+|\s+", compressed))
    matcher = SequenceMatcher(None, [m.group() for m in old], [m.group() for m in new], autojunk=False)
    removed, added = [], []
    for tag, i, j, a, b in matcher.get_opcodes():
        if tag in {"delete", "replace"} and i < j:
            start, end = old[i].start(), old[j - 1].end()
            removed.append({"start": start, "end": end, "text": original[start:end],
                            "reason": "Source/output difference; see algorithm drop records for rules."})
        if tag in {"insert", "replace"} and a < b:
            start, end = new[a].start(), new[b - 1].end()
            added.append({"start": start, "end": end, "text": compressed[start:end]})
    return removed, added


def validate_phrases(text: str, phrases: list[str] | None) -> list[str]:
    """Validate Studio literals without changing compressor input or inference."""
    if phrases is None:
        return []
    if not isinstance(phrases, list) or len(phrases) > 20:
        raise ValueError("Choose at most 20 phrases.")
    for phrase in phrases:
        if not isinstance(phrase, str) or not phrase.strip() or len(phrase) > 200:
            raise ValueError("Each phrase must contain 1 to 200 characters of nonblank text.")
        if phrase not in text:
            raise ValueError(f"Phrase not found exactly in the source prompt: {phrase!r}.")
    return list(dict.fromkeys(phrases))


class CompressionService:
    def __init__(self, model_path: Path | None = None) -> None:
        self.counter = TokenCounter()
        self.model_path = model_path or ROOT / "data/models/crf_compressor.pkl"
        self._lock = threading.Lock()
        self.compressor = Compressor(self.counter, use_crf=True, crf_model_path=self.model_path,
                                     tfidf_path=ROOT / "data/tfidf/hinglish_idf.json")
        self.tagger = None
        linguistic = self.compressor._linguistic
        if linguistic is not None:
            # Upstream swallows prediction failures. This observer prevents claiming
            # CRF execution when only the heuristic prepasses actually ran.
            self.tagger = ObservedTagger(self.model_path, linguistic._tagger.idf_map)
            linguistic._tagger = self.tagger

    def _model_verified(self) -> bool:
        if not self.model_path.is_file():
            return False
        manifest = json.loads((ROOT.parent / "docs/source-manifest.json").read_text(encoding="utf-8"))
        expected = next(row["sha256"] for row in manifest["files"]
                        if row["destination"] == "backend/data/models/crf_compressor.pkl")
        return hashlib.sha256(self.model_path.read_bytes()).hexdigest() == expected

    def analyze(self, text: str, method: str = "heuristic", budget: float = 0.6,
                protected_phrases: list[str] | None = None) -> dict:
        if not text.strip() or len(text) > 12000:
            raise ValueError("Enter 1 to 12,000 characters of nonblank text.")
        if method not in {"heuristic", "crf"}:
            raise ValueError("Choose heuristic or crf.")
        if not math.isfinite(budget) or not 0.1 <= budget <= 1:
            raise ValueError("Budget must be between 0.1 and 1.")
        phrases = validate_phrases(text, protected_phrases)
        started = perf_counter()
        fallback_reason = None
        with self._lock:
            if budget == 1:
                result = CompressResult(original=text, compressed=text, method="passthrough")
            elif method == "crf" and self.tagger is not None and self._model_verified():
                self.tagger.succeeded = False
                result = self.compressor.compress_crf(text)
                if not self.tagger.succeeded:
                    fallback_reason = "CRF prediction unavailable; using the imported heuristic."
                    result = self.compressor.compress_heuristic(text)
                elif result.method != "crf":
                    fallback_reason = "CRF candidate returned unchanged; upstream selected the heuristic."
            else:
                if method == "crf":
                    fallback_reason = "Pinned CRF artifact or runtime unavailable; using the imported heuristic."
                result = self.compressor.compress_heuristic(text)
        # Post-run application guard only: no masking, preprocessing, new token
        # decisions, re-inference or weight changes. The research result is kept.
        candidate_text = result.compressed
        checks = [{"text": phrase, "source_occurrences": text.count(phrase),
                   "candidate_occurrences": candidate_text.count(phrase),
                   "preserved_in_candidate": candidate_text.count(phrase) >= text.count(phrase)}
                  for phrase in phrases]
        protection_fallback = any(not check["preserved_in_candidate"] for check in checks)
        output = text if protection_fallback else candidate_text
        protected = [sp.model_dump() for sp in detect_spans(text)]
        for match in re.finditer(r"\S+", text):
            if is_protected(normalize_chars(match.group())) and not any(
                match.start() < sp["end"] and match.end() > sp["start"] for sp in protected
            ):
                protected.append({"kind": "crf_negation_or_question", "text": match.group(),
                                  "start": match.start(), "end": match.end()})
        for phrase in phrases:
            protected.extend({"kind": "user_phrase", "text": phrase,
                              "start": match.start(), "end": match.end()}
                             for match in re.finditer(re.escape(phrase), text))
        protected.sort(key=lambda sp: sp["start"])
        # Surface checks are observations, not a semantic-equivalence score.
        for span in protected:
            span["preserved"] = output.count(span["text"]) >= text.count(span["text"])
            if phrases:
                span["candidate_preserved"] = candidate_text.count(span["text"]) >= text.count(span["text"])
        for check in checks:
            check["output_occurrences"] = output.count(check["text"])
            check["preserved_in_output"] = check["output_occurrences"] >= check["source_occurrences"]
        original_tokens = self.counter.count(text)
        candidate_tokens = self.counter.count(candidate_text)
        compressed_tokens = original_tokens if protection_fallback else candidate_tokens
        candidate_removed, candidate_added = audit_diff(text, candidate_text)
        removed, added = ([], []) if protection_fallback else (candidate_removed, candidate_added)
        candidate = ({"compressed": candidate_text, "method": result.method,
                      "compressed_tokens": candidate_tokens, "removed_spans": candidate_removed,
                      "added_spans": candidate_added, "drop_records": [d.model_dump() for d in result.drops],
                      "protected_preserved": all(sp["candidate_preserved"] for sp in protected),
                      "fallback_reason": fallback_reason} if phrases else None)
        note = ("Imported guarded lexicon pruning." if result.method == "heuristic" else
                "Imported CRF sequence tagging with phonetic/TF-IDF features and safety gates."
                if result.method == "crf" else "Original text retained.")
        if protection_fallback:
            fallback_reason = "Protection fallback: a selected phrase lost occurrences in the compressor output. " \
                              "The Studio retained the original prompt; the unchanged candidate is available in the audit."
            note = "Post-run Studio literal check, not a research compressor change. Original text retained."
        target_tokens = max(1, math.floor(original_tokens * budget))
        return {
            "original": text, "compressed": output, "requested_method": method,
            "method": "protection_fallback" if protection_fallback else result.method,
            "budget": budget, "target_tokens": target_tokens,
            "budget_met": compressed_tokens <= target_tokens, "budget_tunable": False,
            "budget_note": "Heuristic and CRF have fixed learned/rule decisions, not rate tuning. "
                           "This target is checked, never enforced by truncation. 100% retains the original.",
            "original_tokens": original_tokens, "compressed_tokens": compressed_tokens,
            "saved_tokens": max(0, original_tokens - compressed_tokens),
            "compression_ratio": compressed_tokens / max(1, original_tokens),
            "tokenizer": self.counter.backend, "token_counts_are_billing": False,
            "removed_spans": removed, "added_spans": added, "protected_spans": protected,
            "protected_preserved": all(sp["preserved"] for sp in protected),
            "drop_records": [] if protection_fallback else [d.model_dump() for d in result.drops],
            "protected_phrases": phrases, "phrase_checks": checks,
            "protection_fallback": protection_fallback, "compression_candidate": candidate,
            "fallback_reason": fallback_reason, "note": note,
            "elapsed_ms": round((perf_counter() - started) * 1000, 3),
            "evidence_kind": "local_execution", "source_commit": COMMIT,
            "source_url": source_url("backend/src/gateway/modules/m2_compressor"),
            "limitations": "Regex spans do not detect arbitrary names or all numbers/negations. "
                            "Literal survival does not establish meaning preservation. "
                            "Token counts use a reference tokenizer, not provider billing.",
        }


@lru_cache(maxsize=1)
def get_service() -> CompressionService:
    return CompressionService()
