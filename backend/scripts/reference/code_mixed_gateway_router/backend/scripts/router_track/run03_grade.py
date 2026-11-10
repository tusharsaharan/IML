"""run03: grade cheap_success locally + freeze splits + DECISION_01.

Requires all 3000 queries labeled. Splits 2000/500/500-ish stratified, seed 42.
"""

import csv
import hashlib
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from common import SEED, load_jsonl, track  # noqa: E402
from gateway.modules.m1_pipeline.hinglish import code_mix_ratio  # noqa: E402
from gateway.modules.m4_router.difficulty import DifficultyScorer  # noqa: E402
from gateway.modules.m10_train.reward import reward  # noqa: E402

t = track()
import argparse as _ap

_ap_ = _ap.ArgumentParser()
_ap_.add_argument("--target", type=int, default=1200)
_target = _ap_.parse_args().target
labels_all = load_jsonl(t / "groq_labels.jsonl")
queries_all = load_jsonl(t / "queries.jsonl")[:_target]
want = {q["id"] for q in queries_all}
labels = [r for r in labels_all if r["id"] in want]
queries = queries_all
assert len(labels) == len(queries) == _target, f"incomplete: labels={len(labels)} queries={len(queries)} target={_target}"


def bucket(cm: float) -> str:
    return "low" if cm < 0.25 else ("mid" if cm < 0.5 else "high")


scorer = DifficultyScorer()
rows = []
for r in labels:
    # Primary: does cheap match the premium-proxy answer? (cascade correctness)
    f_prem = reward(r["text"], r["text"], r["premium"], r["cheap"])
    # Secondary (bench rows have a real reference answer): cheap vs reference
    f_ref = reward(r["text"], r["text"], r["ref"], r["cheap"])
    ok = bool(f_prem >= 0.6 or (r["src"] == "bench" and f_ref >= 0.7))
    d = scorer.score(r["text"])
    rows.append({"id": r["id"], "nonconformity": round(d, 6), "cheap_success": ok,
                 "synthetic": False, "group": bucket(code_mix_ratio(r["text"])),
                 "fidelity": round(f_prem, 4), "src": r["src"]})
print("graded", len(rows), "success_rate", round(sum(1 for x in rows if x["cheap_success"]) / len(rows), 4))

rng = random.Random(SEED)
by_g: dict[str, list] = {}
for x in rows:
    by_g.setdefault(x["group"], []).append(x)
train, calib, test = [], [], []
for g, lst in sorted(by_g.items()):
    rng.shuffle(lst)
    n = len(lst)
    n_te, n_ca = max(1, int(0.17 * n)), max(1, int(0.17 * n))
    test += lst[:n_te]
    calib += lst[n_te : n_te + n_ca]
    train += lst[n_te + n_ca :]

(t / "calibration_real.jsonl").write_text("\n".join(json.dumps(x) for x in rows), encoding="utf-8")
(t / "splits.json").write_text(
    json.dumps({"train": [x["id"] for x in train], "calib": [x["id"] for x in calib],
                "test": [x["id"] for x in test], "seed": SEED}, indent=2), encoding="utf-8")
lab = {r["id"]: r for r in labels}
with open(t / "human_check.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["id", "text", "cheap", "premium", "auto_ok", "human_ok"])
    w.writeheader()
    for x in train[:50] + calib[:50] + test[:50]:
        r = lab[x["id"]]
        w.writerow({"id": x["id"], "text": r["text"][:300], "cheap": r["cheap"][:300],
                    "premium": r["premium"][:300], "auto_ok": x["cheap_success"], "human_ok": ""})
h = hashlib.sha256((t / "calibration_real.jsonl").read_bytes()).hexdigest()
(t / "DECISION_01.json").write_text(
    json.dumps({"stage": "01_label", "calibration_sha256": h, "n": len(rows),
                "success_rate": round(sum(1 for x in rows if x["cheap_success"]) / len(rows), 4),
                "proxy": "gpt-oss-120b free (disclosed)", "grading": "auto-only (no human check, zero-touch run)"},
               indent=2), encoding="utf-8")
print(f"train={len(train)} calib={len(calib)} test={len(test)} sha={h[:12]}")
