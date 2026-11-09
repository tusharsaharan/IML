"""Canonical Hinglish lexical-pruning lexicons (single source of truth).

Replaces four divergent hand-rolled filler lists across m2/m10/m12/m5 with one
data-driven package. Every drop decision is recorded as a DropRecord so
compression is auditable (eval tables, debugging, redteam grading).

Guards implemented (why tokens are no longer dropped "randomly"):
- Homograph protection: English words with real Hinglish homographs (you, know,
  sun, log, matlab, like, ...) are never dropped as bare unigrams. "you know"
  and similar drop only as guarded n-grams.
- Vocatives (bhai, dost, ...) drop everywhere EXCEPT kinship/genitive use:
  never when preceded by a possessive pronoun or directly followed by ka/ki/ke
  ("mere bhai ka phone" keeps bhai).
- Position guards: attention-getters (suno, dekho, haan, achha, ...) drop only
  sentence-initially or comma-adjacent, and optionally not as final content
  token (haan as last word = confirmation, kept).
- Tech guard: "matlab" (the software) never dropped when a tech-context word is
  present in the sentence or when it is sentence-initial (rare gloss use).
- Protected spans ([[PSi]] masked code/PII) are never touched: pruning runs on
  masked text and adjacent-to-marker tokens are kept.
"""

from __future__ import annotations

import functools
import json
import re
from pathlib import Path

from gateway.schemas import DropRecord

_LEXICON_DIR = Path(__file__).resolve().parent

_PUNCT = ",.!?:;\"'()[]{}"
_WS = re.compile(r"\s+")
_SENT_SPLIT = re.compile(r"[.!?]+")
_MARKER = re.compile(r"^\[\[PS\d+\]\]$")
_COMMA_RE = re.compile(r"[,;:]")

# Possessives that block vocative-drop when they immediately precede it.
_POSSJECTIVES = frozenset(
    {
        "mera",
        "meri",
        "mere",
        "tera",
        "teri",
        "tere",
        "humara",
        "humari",
        "humare",
        "apna",
        "apni",
        "apne",
        "uska",
        "uski",
        "uske",
        "iska",
        "iski",
        "iske",
        "unka",
        "unki",
        "unke",
    }
)


def _load(name: str) -> dict:
    with (_LEXICON_DIR / name).open(encoding="utf-8") as fh:
        data = json.load(fh)
    return {k: v for k, v in data.items() if not k.startswith("_")}


@functools.cache
def _lexicons() -> dict:
    fillers = _load("fillers.json")
    ngrams = _load("ngram_fillers.json")
    voc = _load("vocatives.json")
    greet = _load("greetings.json")
    return {
        "fillers_unconditional": frozenset(fillers["unconditional"]),
        "fillers_initial_or_comma": dict(fillers["initial_or_comma"]),
        "fillers_comma_or_punct": frozenset(fillers["comma_or_punct"]),
        "fillers_non_initial": frozenset(fillers["non_initial"]),
        "fillers_tech_guarded": fillers["tech_guarded"],
        "ngrams_unconditional": tuple(ngrams["unconditional"]),
        "ngrams_non_initial": tuple(ngrams["non_initial"]),
        "ngrams_comma_or_punct": tuple(ngrams["comma_or_punct"]),
        "vocatives": frozenset(voc["vocatives"]),
        "greetings": tuple(sorted(greet["greetings"], key=len, reverse=True)),
    }


def _strip_punct(token: str) -> str:
    return token.strip(_PUNCT).lower()


def _is_marker(token: str) -> bool:
    return bool(_MARKER.match(token))


def _adjacent_to_marker(tokens: list[str], i: int) -> bool:
    if _is_marker(tokens[i]):
        return True
    if i > 0 and _is_marker(tokens[i - 1]):
        return True
    if i + 1 < len(tokens) and _is_marker(tokens[i + 1]):
        return True
    return False


def _comma_adjacent(tokens: list[str], i: int) -> bool:
    tok = tokens[i]
    if _COMMA_RE.search(tok):
        return True
    if i > 0 and _COMMA_RE.search(tokens[i - 1]) and _strip_punct(tokens[i - 1]):
        return True
    if i + 1 < len(tokens) and _COMMA_RE.search(tokens[i + 1]):
        return True
    return False


def _sentence_positions(tokens: list[str]) -> list[int]:
    """Indices that are sentence-initial (first content token of a sentence)."""
    starts: list[int] = []
    in_sentence = True
    for i, tok in enumerate(tokens):
        if in_sentence:
            starts.append(i)
            in_sentence = False
        if _SENT_SPLIT.search(tok):
            in_sentence = True
    return starts


def _content_indices(tokens: list[str]) -> set[int]:
    return {i for i, t in enumerate(tokens) if _strip_punct(t)}


def _strip_greeting(text: str) -> str:
    """Strip a sentence-initial greeting prefix ('Hello sir, ...' -> '...')."""
    lex = _lexicons()
    for g in lex["greetings"]:
        pat = re.compile(
            r"^\s*" + re.escape(g) + r"\b[\s,!.:]*",
            re.IGNORECASE,
        )
        out = pat.sub("", text, count=1)
        if out != text:
            return out.strip()
    return text.strip()


def _tech_context_in(tokens: list[str], tech_words: frozenset[str]) -> bool:
    return any(_strip_punct(t) in tech_words for t in tokens)


def prune(text: str) -> tuple[str, list[DropRecord]]:
    """Prune Hinglish/English fillers from masked text.

    Input is expected to be span-masked ([[PSi]] markers in place of code/PII).
    Returns (pruned_text, drops) where every dropped token is accounted for.
    """
    lex = _lexicons()
    normalized = _WS.sub(" ", text).strip()
    if not normalized:
        return text, []

    normalized = _strip_greeting(normalized)

    tokens = normalized.split()
    if not tokens:
        return normalized, []

    sent_starts = set(_sentence_positions(tokens))
    content = _content_indices(tokens)
    drops: list[DropRecord] = []
    keep: list[bool] = [True] * len(tokens)

    tech_words = frozenset(w.lower() for w in lex["fillers_tech_guarded"].get("matlab", {}).get("tech_context", []))

    # Pass 1: guarded n-grams (longest-first) — mark member tokens for drop.
    ngram_specs: list[tuple[tuple[str, ...], str]] = []
    for phrase in lex["ngrams_unconditional"]:
        ngram_specs.append((tuple(phrase.split()), "ngram_filler"))
    for phrase in lex["ngrams_non_initial"]:
        ngram_specs.append((tuple(phrase.split()), "ngram_filler_non_initial"))
    for phrase in lex["ngrams_comma_or_punct"]:
        ngram_specs.append((tuple(phrase.split()), "ngram_filler_comma"))
    ngram_specs.sort(key=lambda spec: len(spec[0]), reverse=True)

    ngram_dropped: set[int] = set()
    for phrase, category in ngram_specs:
        n = len(phrase)
        if n == 0 or n > len(tokens):
            continue
        for i in range(len(tokens) - n + 1):
            if any(j in ngram_dropped for j in range(i, i + n)):
                continue
            window = tuple(_strip_punct(t) for t in tokens[i : i + n])
            if window != phrase:
                continue
            non_initial_ok = True
            comma_ok = True
            if category == "ngram_filler_non_initial":
                non_initial_ok = i not in sent_starts
            elif category == "ngram_filler_comma":
                comma_ok = _comma_adjacent(tokens, i) or _adjacent_to_marker(tokens, i)
            if non_initial_ok and comma_ok:
                for j in range(i, i + n):
                    keep[j] = False
                    ngram_dropped.add(j)
                drops.append(DropRecord(token=" ".join(tokens[i : i + n]), category=category, rule="ngram"))

    # Pass 2: unigram fillers + vocatives.
    for i, tok in enumerate(tokens):
        if not keep[i]:
            continue
        low = _strip_punct(tok)
        if not low or _is_marker(tok):
            continue

        # Vocatives: drop unless kinship/genitive use.
        if low in lex["vocatives"]:
            prev = _strip_punct(tokens[i - 1]) if i > 0 else ""
            nxt = _strip_punct(tokens[i + 1]) if i + 1 < len(tokens) else ""
            if prev in _POSSJECTIVES or nxt in {"ka", "ki", "ke"}:
                continue  # kinship/genitive — keep
            keep[i] = False
            drops.append(DropRecord(token=tok, category="vocative", rule="vocative"))
            continue

        # Unconditional fillers.
        if low in lex["fillers_unconditional"]:
            if _adjacent_to_marker(tokens, i):
                continue  # never prune next to protected span
            keep[i] = False
            drops.append(DropRecord(token=tok, category="filler", rule="unconditional"))
            continue

        # Position-guarded fillers (attention-getters / confirmations).
        if low in lex["fillers_initial_or_comma"]:
            guard = lex["fillers_initial_or_comma"][low]
            is_initial = i in sent_starts
            comma_ok = _comma_adjacent(tokens, i) or _adjacent_to_marker(tokens, i)
            not_final_ok = True
            if guard.get("not_final"):
                later = [j for j in content if j > i]
                not_final_ok = bool(later)
            if (is_initial or comma_ok) and not_final_ok:
                if _adjacent_to_marker(tokens, i):
                    continue
                keep[i] = False
                drops.append(
                    DropRecord(
                        token=tok,
                        category="filler_positional",
                        rule="initial_or_comma",
                    )
                )
            continue

        # Comma-adjacent hedges.
        if low in lex["fillers_comma_or_punct"]:
            if _comma_adjacent(tokens, i) or _adjacent_to_marker(tokens, i):
                if not _adjacent_to_marker(tokens, i):
                    keep[i] = False
                    drops.append(DropRecord(token=tok, category="filler_hedge", rule="comma_or_punct"))
            continue

        # Non-initial guarded (matlab-class).
        if low in lex["fillers_non_initial"] or low in lex["fillers_tech_guarded"]:
            guarded = True
            if low in lex["fillers_non_initial"]:
                guarded = i not in sent_starts
            if low in lex["fillers_tech_guarded"]:
                guarded = guarded and not _tech_context_in(tokens, tech_words)
            if guarded and not _adjacent_to_marker(tokens, i):
                keep[i] = False
                drops.append(DropRecord(token=tok, category="filler_guarded", rule="non_initial"))
            continue

    kept_tokens = [t for t, k in zip(tokens, keep, strict=True) if k]
    pruned = _WS.sub(" ", " ".join(kept_tokens)).strip()
    return pruned, drops


def filler_set() -> frozenset[str]:
    """All unconditional unigram+bigram fillers (for stochastic variant generators)."""
    lex = _lexicons()
    words: set[str] = set(lex["fillers_unconditional"])
    words.update(lex["ngrams_unconditional"])
    return frozenset(words)
