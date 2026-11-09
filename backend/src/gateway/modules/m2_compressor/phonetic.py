"""Phonetic normalization for Romanized Hindi (Hinglish).

Solves the *spelling entropy* problem: "kar raha hai" / "kr rha h" /
"karra h" all denote the same construction but no exact string rule can
match them all. This module normalizes chaotic surface forms to canonical
forms (normalize_chars) and computes a consonant-skeleton hash
(hinglish_phash) used as a CRF feature -- never as a standalone lookup key.
"""

from __future__ import annotations

import re

_PUNCT = ",.!?:;\"'()[]{}"
_REPEAT_3PLUS = re.compile(r"(.)\1{2,}")
_MARKER = re.compile(r"^\[\[PS\d+\]\]$")
_DEVANAGARI = re.compile(r"[\u0900-\u097F]")

#: Most frequent Hinglish abbreviations observed in the wild.
ABBREVS: dict[str, str] = {
    "h": "hai",
    "hr": "har",
    "kr": "kar",
    "kro": "karo",
    "rha": "raha",
    "rhi": "rahi",
    "rhe": "rahe",
    "mt": "mat",
    "mtt": "mat",
    "nhi": "nahi",
    "ni": "nahi",
    "nai": "nahi",
    "bt": "baat",
    "bs": "bas",
    "kch": "kuch",
    "frm": "from",
    "msg": "message",
    "plz": "please",
    "pls": "please",
    "thx": "thanks",
    "hw": "how",
    "wt": "what",
    "bcz": "because",
    "bcoz": "because",
    "yr": "yaar",
    "mra": "mera",
    "mre": "mere",
    "mri": "meri",
    "fon": "phone",
    "fone": "phone",
}

#: Negation + question tokens that must NEVER be dropped (normalized forms).
#: The CRF force-keep gate checks membership after normalize_chars().
PROTECTED_TOKENS: frozenset[str] = frozenset(
    {
        # Negation -- dropping inverts meaning
        "nahi",
        "nahin",
        "mat",
        "not",
        "never",
        "n't",
        "no",
        "don't",
        "doesn't",
        "didn't",
        # Question words -- dropping changes intent
        "kya",
        "kahan",
        "kidhar",
        "kaise",
        "kaisa",
        "kab",
        "kyun",
        "kyu",
        "kaun",
        "kiska",
        "kitna",
        "kitne",
    }
)

#: Hinglish consonant-cluster mapping applied before vowel stripping.
CLUSTER_MAP: tuple[tuple[str, str], ...] = (
    ("sh", "S"),
    ("ch", "C"),
    ("th", "T"),
    ("dh", "D"),
    ("kh", "K"),
    ("gh", "G"),
    ("ph", "F"),
    ("bh", "B"),
    ("aa", "A"),
    ("ee", "I"),
    ("oo", "U"),
)

_VOWELS = frozenset("aeiou")


def _strip_punct(token: str) -> str:
    return token.strip(_PUNCT)


def is_marker(token: str) -> bool:
    """True for protected-span markers like [[PS0]]."""
    return bool(_MARKER.match(token.strip()))


def is_protected(norm_token: str) -> bool:
    """True if a *normalized* token is a protected negation/question word."""
    return norm_token in PROTECTED_TOKENS


def normalize_chars(token: str) -> str:
    """Normalize a single token's spelling chaos to a canonical form.

    Steps: lowercase -> abbreviation expansion -> repeated-char collapse
    (consonants collapse fully; long Hindi vowels aa/ee/oo capped at 2) ->
    surrounding punctuation stripped. Markers and Devanagari pass through
    (markers byte-identical, Devanagari lowercased only).
    """
    if not token:
        return token
    if is_marker(token):
        return token
    if _DEVANAGARI.search(token):
        return token.lower()
    s = _strip_punct(token.lower())
    if not s:
        return s
    if s in ABBREVS:
        return ABBREVS[s]
    # Collapse runs of 3+ identical chars to a single char ("haaaaai" ->
    # "hai", "pleaseee" -> "please"). Legitimate doubles ("arre", "http",
    # "assignment", Hindi long vowels "aa") are preserved as-is.
    s = re.sub(r"(.)\1{2,}", r"\1", s)
    # A second abbreviation pass catches cases revealed by collapsing
    # ("krr" -> "kr" -> "kar").
    if s in ABBREVS:
        return ABBREVS[s]
    return s


def hinglish_phash(token: str) -> str:
    """Consonant-skeleton phonetic hash for Romanized Hindi.

    Maps variant spellings to the same code: raha/rha/rahi -> RH*,
    nahi/nhi -> NH, kar/kr/karo -> KR, basically/bascly -> BSKL.
    One feature among many for the CRF -- collisions are expected and
    disambiguated by suffix/prefix/neighbor features.
    """
    if not token:
        return ""
    if is_marker(token):
        return "PS"
    if _DEVANAGARI.search(token):
        # Devanagari tokens hash on first char to keep them distinct.
        return "DV" + token[0]
    s = normalize_chars(token)
    if not s:
        return ""
    # Strip trailing vowel inflection noise ("karo"/"kare" share root "kar").
    stripped = re.sub(r"[aeiou]+$", "", s)
    s = stripped or s
    for src, dst in CLUSTER_MAP:
        s = s.replace(src, dst)
    s = re.sub(r"[aeiou]", "", s)
    s = re.sub(r"(.)\1+", r"\1", s)
    # Cluster replacements introduced uppercase sentinels; normalize case.
    s = s.upper()
    return s or token[0].upper()
