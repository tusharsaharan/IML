"""run06: conformal-safe vs pure-RL thresholds on CALIB (no test touch)."""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from common import load_jsonl, track  # noqa: E402
from gateway.modules.m3_conformal.conformal import ConformalCalibrator  # noqa: E402
from gateway.schemas import CalibSample  # noqa: E402

t = track()
rows = load_jsonl(t / "calibration_real.jsonl")
by_id = {r["id"]: r for r in rows}
splits = json.loads((t / "splits.json").read_text())
ca = splits["calib"]
h = np.array([by_id[i]["nonconformity"] for i in ca])
y = np.array([0 if by_id[i]["cheap_success"] else 1 for i in ca])

ids_all = json.loads((t / "feat_ids.json").read_text())
X_all = np.load(t / "X_all.npy")
X = {rid: X_all[k] for k, rid in enumerate(ids_all)}
try:
    import pickle

    lr = pickle.load(open(t / "logreg.pkl", "rb"))
    p_learned = lr.predict_proba(np.stack([X[i] for i in ca]))[:, 1]
except Exception as e:  # noqa: BLE001
    print("supervised reload fallback:", e)
    p_learned = h


def to_samples(scores, ids):
    return [CalibSample(id=i, nonconformity=round(float(s), 6),
                        cheap_success=bool(by_id[i]["cheap_success"]),
                        group=by_id[i]["group"], synthetic=False) for i, s in zip(ids, scores)]


out = {}
for name, sc in [("heuristic", h), ("learned", p_learned)]:
    cal = ConformalCalibrator(alpha=0.05, delta=0.05, method="fixed_sequence").calibrate(to_samples(sc, ca))
    out[name] = {"tau": round(cal.threshold, 4), "risk_hat": round(cal.risk_hat, 4),
                 "risk_bound": round(cal.risk_bound, 4),
                 "cheap_share": round(float(sum(1 for v in sc if v < cal.threshold) / len(sc)), 4)}
    print(name, out[name])
cal_m = ConformalCalibrator(alpha=0.05, delta=0.05).calibrate(to_samples(p_learned, ca))
out["mondrian"] = {"taus": {k: round(v, 4) for k, v in cal_m.group_thresholds.items()},
                   "risk_bound": round(cal_m.risk_bound, 4), "is_mondrian": cal_m.is_mondrian}
print(out["mondrian"])
SAVE, LAM = 0.7, 2.0
best = max((((p_learned < th).astype(float) * (SAVE - LAM * y)).mean(), th) for th in [i / 200 for i in range(201)])
out["pure_rl"] = {"tau": round(float(best[1]), 4), "mean_reward": round(float(best[0]), 4), "guarantee": None}
print("pure_rl", out["pure_rl"])
(t / "thresholds.json").write_text(json.dumps({"alpha": 0.05, "proxy": True, "arms": out}, indent=2), encoding="utf-8")
(t / "DECISION_04.json").write_text(json.dumps(
    {"stage": "04_conformal", "frozen": "thresholds.json", "note": "run07 evaluates once on TEST; no retrain after"},
    indent=2), encoding="utf-8")
print("FROZEN thresholds.json")
