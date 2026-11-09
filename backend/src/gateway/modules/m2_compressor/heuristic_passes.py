"""Fast heuristic pre-pruning (Stage 3 of the CRF pipeline).

Three safe, context-free operations that run BEFORE the CRF on masked text:
greeting strip, reduplication collapse, and a tiny unconditional filler set.
Everything context-dependent (yaar/matlab/basically/toh/na/like) belongs to
the CRF, not here.
"""

from __future__ import annotations

import re

from gateway.lexicons import _lexicons as _load_lexicons
from gateway.modules.m2_compressor.phonetic import is_marker, normalize_chars
from gateway.schemas import DropRecord

#: Universally safe drops -- interjections/hesitations with no homograph risk.
UNCONDITIONAL_FILLERS: frozenset[str] = frozenset(
    {"arre", "arrey", "arey", "um", "uh", "umm", "err", "hmm"}
)

_ECHO_INITIALS = frozenset("vw")


def strip_greeting_enhanced(text: str) -> tuple[str, DropRecord | None]:
    """Strip a sentence-initial greeting, phonetically tolerant.

    Matches greeting entries against normalized token prefixes so variants
    like "namste"/"namastey"/"heyy" are caught. A message that IS only a
    greeting is returned unchanged (nothing to compress to).
    """
    lex = _load_lexicons()
    greetings: tuple[str, ...] = lex["greetings"]  # longest-first
    stripped = text.strip()
    if not stripped:
        return text, None
    lowered = stripped.lower()
    # Greeting-only message -> keep.
    if normalize_chars(lowered.strip(",.!?:; ")) in {
        normalize_chars(g) for g in greetings
    } or lowered.strip(",.!?:; ") in {g.lower() for g in greetings}:
        return stripped, None
    first_drop: DropRecord | None = None
    # Loop so stacked greetings ("hello sir,", "namaste bhai,") strip fully.
    for _ in range(3):
        matched = False
        for g in greetings:
            pat = re.compile(r"^\s*" + re.escape(g) + r"\b[\s,!.:]*", re.IGNORECASE)
            out = pat.sub("", stripped, count=1)
            if out != stripped:
                out = out.strip()
                if not out:
                    return text.strip(), None
                stripped = out
                if first_drop is None:
                    first_drop = DropRecord(token=g, category="greeting", rule="greeting_strip")
                matched = True
                break
        if not matched:
            break
    if first_drop is not None:
        return stripped, first_drop
    # Phonetic fallback: compare normalized first-token run against
    # normalized greeting entries (catches "namste," / "heyy sir,").
    tokens = stripped.split()
    norm_tokens = [normalize_chars(t) for t in tokens]
    norm_greets = {normalize_chars(g): g for g in greetings}
    # Multi-word greetings ("good morning") need a 2-token lookahead.
    for width in (2, 1):
        if len(norm_tokens) >= width:
            cand = " ".join(norm_tokens[:width]).strip(",.!?:; ")
            if cand in norm_greets:
                rest = " ".join(tokens[width:]).lstrip(",.!?:; ").strip()
                if not rest:
                    return stripped, None
                return rest, DropRecord(
                    token=" ".join(tokens[:width]),
                    category="greeting",
                    rule="greeting_strip_phonetic",
                )
    return stripped, None


def collapse_reduplication(tokens: list[str]) -> tuple[list[str], list[DropRecord]]:
    """Collapse adjacent exact reduplication (jaldi jaldi) and echo
    reduplication (chai-vai, kaam-vaam). Comparison is on normalized forms
    so "jaldi jaldi" with spelling wobble still collapses."""
    out: list[str] = []
    drops: list[DropRecord] = []
    i = 0
    while i < len(tokens):
        if i + 1 < len(tokens) and not is_marker(tokens[i]) and not is_marker(tokens[i + 1]):
            norm_i = normalize_chars(tokens[i])
            norm_j = normalize_chars(tokens[i + 1])
            if norm_i and norm_i == norm_j:
                drops.append(
                    DropRecord(token=tokens[i + 1], category="reduplication", rule="exact")
                )
                out.append(tokens[i])
                i += 2
                continue
            if (
                norm_j
                and norm_j[0] in _ECHO_INITIALS
                and len(norm_i) > 2
                and len(norm_j) > 2
                and norm_i[-2:] == norm_j[-2:]
            ):
                drops.append(
                    DropRecord(token=tokens[i + 1], category="reduplication", rule="echo")
                )
                out.append(tokens[i])
                i += 2
                continue
        out.append(tokens[i])
        i += 1
    return out, drops


def strip_unconditional_fillers(tokens: list[str]) -> tuple[list[str], list[DropRecord]]:
    """Drop only the tiny UNCONDITIONAL_FILLERS set (normalized comparison).

    Markers pass through untouched.
    """
    out: list[str] = []
    drops: list[DropRecord] = []
    for tok in tokens:
        if is_marker(tok):
            out.append(tok)
            continue
        if normalize_chars(tok) in UNCONDITIONAL_FILLERS:
            drops.append(DropRecord(token=tok, category="filler", rule="unconditional"))
            continue
        out.append(tok)
    return out, drops
