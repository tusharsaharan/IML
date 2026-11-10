"""run01: build frozen 3000-query set (deterministic fluff paraphrases, seed 42)."""

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from common import DATA, SEED, track  # noqa: E402


def load(p: Path):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


bench = load(DATA / "benchmark.sample.jsonl")
seeds = load(DATA / "seed_hinglish.jsonl")
humans = load(DATA / "seed_human.jsonl")

FLUFF = ["yaar", "matlab", "bhai", "arre", "sun na", "dekho na", "actually", "basically"]
rng = random.Random(SEED)
queries: list[dict] = []
for r in bench:
    queries.append({"id": r["id"], "text": r["original"], "ref": r["reference_answer"], "src": "bench"})
for r in seeds:
    queries.append({"id": r["id"], "text": r["text"], "ref": r["text"], "src": "seed"})
for r in humans:
    queries.append({"id": r["id"], "text": r["text"], "ref": r["text"], "src": "human"})
base = [q["text"] for q in queries]
i = 0
while len(queries) < 3000:
    t = base[i % len(base)]
    toks = t.split()
    if rng.random() < 0.5:
        toks = [w for w in toks if w.lower() not in set(FLUFF)]
    else:
        toks = toks + [rng.choice(FLUFF)]
    queries.append({"id": f"aug-{i:04d}", "text": " ".join(toks), "ref": base[i % len(base)], "src": "aug"})
    i += 1

t = track()
with open(t / "queries.jsonl", "w", encoding="utf-8") as fh:
    for q in queries:
        fh.write(json.dumps(q, ensure_ascii=False) + "\n")
print("queries:", len(queries), "->", t / "queries.jsonl")
