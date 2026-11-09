from __future__ import annotations

import re
import unicodedata
from typing import Any

from pydantic import BaseModel, Field

from gateway.modules.m12_semantic.embeddings import HASH_THRESHOLD, SemanticEmbedder, get_embedder

# Romanized Hinglish → English gloss. Precision-oriented: only words whose
# meaning is unambiguous out of context. Unknown words pass through
# untouched (counted in `uncovered`) rather than guessed.
HINGLISH_GLOSS_MAP: dict[str, str] = {
    # pronouns / address
    "mera": "my", "meri": "my", "mere": "my", "tera": "your", "teri": "your",
    "tere": "your", "mujhe": "me", "mujhko": "me", "tujhe": "you", "hum": "we",
    "aap": "you", "tum": "you", "yeh": "this", "ye": "this", "woh": "that",
    "vo": "that", "kya": "what",
    # verbs / asks
    "kar": "do", "karo": "do", "karna": "to do", "karun": "do", "karoon": "do",
    "batao": "tell", "bata": "tell", "bhejo": "send", "bhej": "send",
    "dedo": "give", "chahiye": "need", "chahie": "need", "samajh": "understand",
    "samjha": "understood", "aaya": "came", "aayi": "came", "gaya": "went",
    "gayi": "went", "hoga": "will be", "hogi": "will be", "bharna": "to fill",
    "likhna": "to write", "padhna": "to read", "milega": "will get",
    "lagegi": "will apply", "lagega": "will apply", "chal": "go",
    "nikalna": "to find", "nikal": "find", "solve": "solve",
    # being / negation / tense
    "hai": "is", "hain": "are", "tha": "was", "thi": "was", "the": "were",
    "ho": "be", "raha": "is", "rahi": "is", "rahe": "are", "nahi": "not",
    "nahin": "not", "haan": "yes", "matlab": "", "wala": "", "wali": "",
    "wale": "", "ka": "of", "ki": "of", "ke": "of", "ko": "to",
    "mein": "in", "me": "in", "par": "on", "se": "from", "tak": "until",
    "liye": "for", "bhi": "also", "hi": "itself", "na": "", "toh": "so",
    "kab": "when", "kaise": "how", "kahan": "where", "kyun": "why",
    "kaun": "who", "kitna": "how much", "kitni": "how much", "kitne": "how many",
    "jaldi": "quickly", "abhi": "right now", "aaj": "today", "kal": "tomorrow",
    # support / campus domain
    "sawal": "question", "jawab": "answer", "form": "form", "fees": "fees",
    "email": "email", "phone": "phone", "paise": "money", "paisa": "money",
    "din": "days", "raat": "night", "exam": "exam", "sir": "sir",
}

# Fillers with no propositional content — safe to drop in a gloss.
_FILLERS = frozenset({"yaar", "arre", "bhai", "sun", "na", "dekho", "like", "basically", "actually", "you", "know"})

_PS = re.compile(r"\[\[PS\d+\]\]")
_WORD_OR_PS = re.compile(r"\[\[PS\d+\]\]|[A-Za-z\u0900-\u097f0-9']+")


class TranslationResult(BaseModel):
    original: str = ""
    gloss: str = ""
    is_rule_based: bool = True
    coverage: float = 0.0
    uncovered: list[str] = Field(default_factory=list)
    similarity: float = 0.0
    preserves_meaning: bool = False
    backend: str = "rule"


def normalize_hinglish(text: str) -> str:
    """Unicode + whitespace normalization. Case and entities untouched."""
    text = unicodedata.normalize("NFKC", text or "")
    return re.sub(r"\s+", " ", text).strip()


def rule_gloss(text: str) -> tuple[str, float, list[str]]:
    """Word-level Hinglish→English gloss with protected-span passthrough.

    Entities/code/amounts are masked via the M2 safety-span detector so they
    are never translated or lowercased, then re-injected verbatim.
    Returns (gloss, coverage, uncovered_words).
    """
    from gateway.modules.m2_compressor.safety_span import mask, reinject

    text = normalize_hinglish(text)
    if not text:
        return "", 0.0, []
    masked, spans = mask(text)
    n_words = known = 0
    uncovered: list[str] = []

    def _sub(m: re.Match[str]) -> str:
        nonlocal n_words, known
        tok = m.group(0)
        if _PS.fullmatch(tok):
            return tok
        low = tok.lower()
        n_words += 1
        if low in _FILLERS:
            known += 1
            return ""
        if low in HINGLISH_GLOSS_MAP:
            known += 1
            return HINGLISH_GLOSS_MAP[low]
        uncovered.append(tok)
        return tok

    glossed = _WORD_OR_PS.sub(_sub, masked)
    glossed = re.sub(r"\s+", " ", glossed).strip()
    glossed, _ = reinject(glossed, spans)
    coverage = round(known / max(1, n_words), 6)
    return glossed, coverage, sorted(set(uncovered))


def translation_messages(text: str) -> list[dict[str, Any]]:
    """Prompt for the LLM translation path (used when NOT in dry-run)."""
    return [
        {
            "role": "system",
            "content": (
                "Translate Hinglish (Hindi-English code-mixed, romanized or Devanagari) "
                "to natural English. Preserve every task-critical detail exactly: names, "
                "numbers, amounts, emails, phones, code, dates. Drop only pure fillers "
                "(yaar, arre, matlab). Output the translation only, no commentary."
            ),
        },
        {"role": "user", "content": text},
    ]


async def translate_hinglish(
    text: str,
    client: Any | None = None,
    embedder: SemanticEmbedder | None = None,
    threshold: float = HASH_THRESHOLD,
) -> TranslationResult:
    """Gloss Hinglish to English, verifying meaning with embeddings.

    * No client / mock client → rule-based gloss, ``is_rule_based=True``.
    * Real client → LLM translation, embedding-verified, ``is_rule_based=False``.
    Never raises for translation failure: falls back to the rule gloss.
    """
    emb = embedder or get_embedder()
    rule_text, coverage, uncovered = rule_gloss(text)
    use_llm = client is not None and type(client).__name__ != "MockLLMClient"
    if not use_llm:
        sim = emb.similarity(text, rule_text) if rule_text else 0.0
        return TranslationResult(
            original=text, gloss=rule_text, is_rule_based=True, coverage=coverage,
            uncovered=uncovered, similarity=sim, preserves_meaning=sim >= threshold,
            backend="rule",
        )
    try:
        res = await client.chat(translation_messages(text), temperature=0.0)
        gloss = (res.content or "").strip()
        if not gloss:
            raise ValueError("empty translation")
        sim = emb.similarity(text, gloss)
        return TranslationResult(
            original=text, gloss=gloss, is_rule_based=False, coverage=1.0,
            uncovered=[], similarity=sim, preserves_meaning=sim >= threshold,
            backend=getattr(client, "model", "llm"),
        )
    except Exception:
        sim = emb.similarity(text, rule_text) if rule_text else 0.0
        return TranslationResult(
            original=text, gloss=rule_text, is_rule_based=True, coverage=coverage,
            uncovered=uncovered, similarity=sim, preserves_meaning=sim >= threshold,
            backend="rule-fallback",
        )


def gloss_sync(text: str, embedder: SemanticEmbedder | None = None) -> TranslationResult:
    """Offline rule-based gloss (no event loop needed)."""
    emb = embedder or get_embedder()
    gloss, coverage, uncovered = rule_gloss(text)
    sim = emb.similarity(text, gloss) if gloss else 0.0
    return TranslationResult(
        original=text, gloss=gloss, is_rule_based=True, coverage=coverage,
        uncovered=uncovered, similarity=sim, preserves_meaning=sim >= HASH_THRESHOLD,
        backend="rule",
    )
