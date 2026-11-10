"""run04: supervised P(fail|x) — LogReg vs XGB on [5 heuristic + 384 MiniLM]. CPU OK."""

import json
import pickle
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from common import load_jsonl, track  # noqa: E402
from gateway.modules.m4_router.difficulty import DifficultyScorer  # noqa: E402
from gateway.modules.m11_calibration.ece import expected_calibration_error  # noqa: E402

t = track()
rows = load_jsonl(t / "calibration_real.jsonl")
lab = {r["id"]: r for r in load_jsonl(t / "groq_labels.jsonl")}
splits = json.loads((t / "splits.json").read_text())
by_id = {r["id"]: r for r in rows}
scorer = DifficultyScorer()

from sentence_transformers import SentenceTransformer  # noqa: E402

ids_all = [r["id"] for r in rows]
if (t / "X_all.npy").exists() and (t / "feat_ids.json").exists() and json.loads((t / "feat_ids.json").read_text()) == ids_all:
    print("reusing cached embeddings")
    E = np.load(t / "X_all.npy")[:, 5:]
else:
    enc = SentenceTransformer("all-MiniLM-L6-v2")
    E = enc.encode([lab[i]["text"] for i in ids_all], batch_size=32, show_progress_bar=True, normalize_embeddings=True)


def h5(rid):
    f = scorer.features(lab[rid]["text"])
    return [f.code_mix_ratio, f.entity_density, min(1.0, f.math_marker_count / 3.0),
            min(1.0, f.char_count / 400.0), len(lab[rid]["text"].split()) / 50.0]


FEAT = {rid: np.concatenate([np.array(h5(rid), dtype=np.float32), E[k]]) for k, rid in enumerate(ids_all)}
Y = {r["id"]: (0 if r["cheap_success"] else 1) for r in rows}
np.save(t / "X_all.npy", np.stack([FEAT[i] for i in ids_all]))
(t / "feat_ids.json").write_text(json.dumps(ids_all), encoding="utf-8")

from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import average_precision_score, roc_auc_score  # noqa: E402

tr, ca = splits["train"], splits["calib"]
Xtr = np.stack([FEAT[i] for i in tr])
ytr = np.array([Y[i] for i in tr])
Xca = np.stack([FEAT[i] for i in ca])
yca = np.array([Y[i] for i in ca])
h_ca = np.array([by_id[i]["nonconformity"] for i in ca])
h_tr = np.array([by_id[i]["nonconformity"] for i in tr])
print("heuristic AUROC train/calib:", round(roc_auc_score(ytr, h_tr), 4), round(roc_auc_score(yca, h_ca), 4))

clf = LogisticRegression(max_iter=1000).fit(Xtr, ytr)
p_ca = clf.predict_proba(Xca)[:, 1]
print("logreg AUROC:", round(roc_auc_score(yca, p_ca), 4),
      "AUPRC:", round(average_precision_score(yca, p_ca), 4),
      "ECE:", round(expected_calibration_error(1 - p_ca, [bool(1 - y) for y in yca]), 4))

import xgboost as xgb  # noqa: E402

gx = xgb.XGBClassifier(n_estimators=300, max_depth=5, learning_rate=0.05, subsample=0.8, n_jobs=4, eval_metric="logloss")
gx.fit(Xtr, ytr)
g_ca = gx.predict_proba(Xca)[:, 1]
print("xgb AUROC:", round(roc_auc_score(yca, g_ca), 4),
      "ECE:", round(expected_calibration_error(1 - g_ca, [bool(1 - y) for y in yca]), 4))

winner = "xgb" if roc_auc_score(yca, g_ca) >= roc_auc_score(yca, p_ca) else "logreg"
pickle.dump(clf, open(t / "logreg.pkl", "wb"))
gx.save_model(str(t / "xgb.json"))
(t / "DECISION_02.json").write_text(json.dumps(
    {"stage": "02_supervised", "winner": winner,
     "auroc_heuristic": round(float(roc_auc_score(yca, h_ca)), 4),
     "auroc_logreg": round(float(roc_auc_score(yca, p_ca)), 4),
     "auroc_xgb": round(float(roc_auc_score(yca, g_ca)), 4)},
    indent=2), encoding="utf-8")
print("winner:", winner)
