"""Build the TF-IDF information-content map (offline, run once).

Usage:
    python scripts/build_tfidf.py --prompts data/training/prompts.jsonl \\
        --out data/tfidf/hinglish_idf.json

Token keys are normalize_chars() forms; values are log-IDF normalized to
[0,1]. High = rare/informative (keep); low = common/redundant.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT / "src"))

from gateway.modules.m2_compressor.phonetic import normalize_chars  # noqa: E402
from gateway.modules.m2_compressor.safety_span import mask  # noqa: E402


def build(prompts: list[str]) -> dict[str, float]:
    n = len(prompts)
    df: Counter[str] = Counter()
    for text in prompts:
        masked, _ = mask(text)
        toks = {normalize_chars(t) for t in masked.split() if normalize_chars(t)}
        for tok in toks:
            df[tok] += 1
    idf = {tok: math.log(n / (1 + c)) for tok, c in df.items()}
    peak = max(idf.values()) if idf else 1.0
    return {tok: round(v / peak, 4) for tok, v in idf.items()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompts", default="data/training/prompts.jsonl")
    ap.add_argument("--out", default="data/tfidf/hinglish_idf.json")
    args = ap.parse_args()

    prompts_path = Path(args.prompts)
    if not prompts_path.is_absolute():
        prompts_path = BACKEND_ROOT / prompts_path
    texts = [
        json.loads(line)["text"]
        for line in prompts_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    idf = build(texts)
    out = Path(args.out)
    if not out.is_absolute():
        out = BACKEND_ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(idf, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(idf)} entries -> {out}")


if __name__ == "__main__":
    main()
