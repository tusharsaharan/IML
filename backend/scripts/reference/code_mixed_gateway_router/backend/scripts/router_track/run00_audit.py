"""run00: audit — heuristic scores vs synthetic calibration gap + freeze query list."""

import hashlib
import json
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "src"))

from common import DATA, track  # noqa: E402
from gateway.modules.m1_pipeline.hinglish import code_mix_ratio  # noqa: E402
from gateway.modules.m4_router.difficulty import DifficultyScorer  # noqa: E402
from gateway.service import default_calibration  # noqa: E402


def load(p):
    import pathlib

    p = pathlib.Path(p)
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


bench = load(DATA / "benchmark.sample.jsonl")
seeds = load(DATA / "seed_hinglish.jsonl")
humans = load(DATA / "seed_human.jsonl")
print(f"bench={len(bench)} seeds={len(seeds)} humans={len(humans)}")

scorer = DifficultyScorer()
texts = [r.get("original", r.get("text", "")) for r in (bench + seeds + humans)]
scores = [scorer.score(t) for t in texts]
print(f"heuristic d(x): n={len(scores)} mean={sum(scores) / max(1, len(scores)):.4f}")

syn = default_calibration(n=2000, seed=42)
print(f"synthetic calib: n={len(syn)} fail_rate={sum(1 for s in syn if not s.cheap_success) / len(syn):.3f} (by construction 0.30)")

t = track()
qlist = sorted({r.get("id", f"row-{i}") for i, r in enumerate(bench + seeds + humans)})
sha = hashlib.sha256(json.dumps(qlist, sort_keys=True).encode()).hexdigest()
(t / "query_list.json").write_text(json.dumps({"ids": qlist, "sha256": sha, "n": len(qlist)}, indent=2))
(t / "DECISION_00.json").write_text(
    json.dumps(
        {"stage": "00_audit", "query_sha256": sha, "n_queries": len(qlist),
         "heuristic_mean": round(sum(scores) / max(1, len(scores)), 4), "synthetic_fail_rate": 0.30},
        indent=2,
    )
)
print("FROZEN query_sha256:", sha, "n =", len(qlist))
