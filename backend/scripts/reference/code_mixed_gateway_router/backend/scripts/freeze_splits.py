"""Freeze train/calib/test splits for the free router track (anti-spin).

Reads backend/data/calibration_real.jsonl (written by colab_01_label),
stratifies by group (low/mid/high), splits with seed 42, writes splits.json
+ DECISION_01_local.json with sha256 of the calibration file.

Usage:
    python backend/scripts/freeze_splits.py
    python backend/scripts/freeze_splits.py --check   # CI: assert hash matches

Rule: after splits.json exists, NB05 test IDs must never be used for training.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DATA = BACKEND / "data"
CALIB = DATA / "calibration_real.jsonl"
SPLITS = DATA / "splits.json"


def main(check: bool = False) -> int:
    if not CALIB.exists():
        print(f"missing {CALIB} — run colab_01_label first (free Groq labels)")
        return 2
    rows = [json.loads(l) for l in CALIB.read_text(encoding="utf-8").splitlines() if l.strip()]
    sha = hashlib.sha256(CALIB.read_bytes()).hexdigest()
    by_g: dict[str, list[dict]] = {}
    for r in rows:
        by_g.setdefault(r.get("group", "all"), []).append(r)
    rng = random.Random(42)
    train, calib, test = [], [], []
    for g, lst in sorted(by_g.items()):
        rng.shuffle(lst)
        n = len(lst)
        n_te = max(1, int(0.17 * n))
        n_ca = max(1, int(0.17 * n))
        test += [x["id"] for x in lst[:n_te]]
        calib += [x["id"] for x in lst[n_te : n_te + n_ca]]
        train += [x["id"] for x in lst[n_te + n_ca :]]
    payload = {"train": train, "calib": calib, "test": test, "seed": 42, "calibration_sha256": sha}
    if check:
        if not SPLITS.exists():
            print("splits.json missing")
            return 1
        cur = json.loads(SPLITS.read_text(encoding="utf-8"))
        ok = cur.get("calibration_sha256") == sha
        print("check:", "OK" if ok else f"MISMATCH {cur.get('calibration_sha256')} != {sha}")
        return 0 if ok else 1
    SPLITS.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (DATA / "DECISION_01_local.json").write_text(
        json.dumps({"stage": "01_label_frozen", "sha256": sha, "n": len(rows)}, indent=2), encoding="utf-8"
    )
    print(f"frozen n={len(rows)} train={len(train)} calib={len(calib)} test={len(test)} sha={sha[:12]}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    sys.exit(main(check=args.check))
