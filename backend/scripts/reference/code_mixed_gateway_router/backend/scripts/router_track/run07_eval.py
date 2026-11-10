"""run07: ONE-SHOT holdout eval on TEST. Refuses to re-run (anti-spin).

After this runs once, any new idea goes to Future Work — no retraining.
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from common import load_jsonl, track  # noqa: E402
from gateway.pricing import CHEAP_PER_1K_USD, PREMIUM_PER_1K_USD  # noqa: E402

t = track()
assert not (t / "DECISION_05.json").exists(), "TEST already evaluated once — no re-runs (see Future Work)."
th = json.loads((t / "thresholds.json").read_text())
splits = json.loads((t / "splits.json").read_text())
rows = load_jsonl(t / "calibration_real.jsonl")
by_id = {r["id"]: r for r in rows}
te = splits["test"]

h_te = np.array([by_id[i]["nonconformity"] for i in te])
y_te = np.array([0 if by_id[i]["cheap_success"] else 1 for i in te])
groups = [by_id[i]["group"] for i in te]
ids_all = json.loads((t / "feat_ids.json").read_text())
X_all = np.load(t / "X_all.npy")
X = {rid: X_all[k] for k, rid in enumerate(ids_all)}
try:
    import pickle

    lr = pickle.load(open(t / "logreg.pkl", "rb"))
    p_te = lr.predict_proba(np.stack([X[i] for i in te]))[:, 1]
except Exception as e:  # noqa: BLE001
    print("fallback heuristic:", e)
    p_te = h_te

from sklearn.metrics import roc_auc_score  # noqa: E402

print("TEST AUROC heuristic/learned:", round(roc_auc_score(y_te, h_te), 4), round(roc_auc_score(y_te, p_te), 4))

arms = th["arms"]
taus = {"heuristic_safe": (h_te, arms["heuristic"]["tau"]),
        "learned_safe": (p_te, arms["learned"]["tau"]),
        "pure_rl": (p_te, arms["pure_rl"]["tau"])}
mt = arms["mondrian"]["taus"]
cheap_m = np.array([1 if p < mt.get(g, arms["learned"]["tau"]) else 0 for p, g in zip(p_te, groups)])


def metrics(mask):
    err = float((mask * y_te).sum() / len(y_te))
    share = float(mask.mean())
    toks = 400
    cost = share * toks * CHEAP_PER_1K_USD / 1000 + (1 - share) * toks * PREMIUM_PER_1K_USD / 1000
    base = toks * PREMIUM_PER_1K_USD / 1000
    return {"error": round(err, 4), "cheap_share": round(share, 4), "saving": round((base - cost) / base, 4)}


rep = {}
masks = {}
for name, (sc, tau) in taus.items():
    masks[name] = (sc < tau).astype(int)
    rep[name] = metrics(masks[name])
    print(name, "tau", tau, rep[name])
masks["learned_mondrian"] = cheap_m
rep["learned_mondrian"] = metrics(cheap_m)
print("learned_mondrian", rep["learned_mondrian"])

rng = np.random.default_rng(42)
for name in list(rep):
    errs = []
    for _ in range(1000):
        idx = rng.integers(0, len(te), len(te))
        errs.append(float((masks[name][idx] * y_te[idx]).sum() / len(idx)))
    rep[name]["error_ci95"] = [round(float(np.quantile(errs, 0.025)), 4), round(float(np.quantile(errs, 0.975)), 4)]
rep["price_of_safety"] = round(rep["pure_rl"]["saving"] - rep["learned_safe"]["saving"], 4)
rep["proxy"] = True
rep["test_n"] = len(te)
rep["grading"] = "auto-only (zero-touch run, no human check)"
(t / "eval_report.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
(t / "DECISION_05.json").write_text(json.dumps(
    {"stage": "05_eval_done", "test_n": len(te), "frozen_report": "eval_report.json",
     "rule": "DO NOT retrain after this"}, indent=2), encoding="utf-8")
print(rep)
