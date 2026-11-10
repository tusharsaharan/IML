"""run05: cost-aware contextual bandit head (torch CPU) + frozen lambda report."""

import json
import pickle
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from common import load_jsonl, track  # noqa: E402

t = track()
rows = load_jsonl(t / "calibration_real.jsonl")
splits = json.loads((t / "splits.json").read_text())
ids_all = json.loads((t / "feat_ids.json").read_text())
X_all = np.load(t / "X_all.npy")
X = {rid: X_all[k] for k, rid in enumerate(ids_all)}
FAIL = {r["id"]: (0 if r["cheap_success"] else 1) for r in rows}
SAVE, LAM_TRAIN = 0.7, 2.0
device = "cpu"


class Head(nn.Module):
    def __init__(self, d):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(d, 128), nn.ReLU(), nn.Dropout(0.2), nn.Linear(128, 2))

    def forward(self, x):
        return self.net(x)


D = len(next(iter(X.values())))
head = Head(D).to(device)
opt = torch.optim.AdamW(head.parameters(), lr=1e-3, weight_decay=1e-4)
tr = splits["train"]
Xtr = torch.tensor(np.stack([X[i] for i in tr]), dtype=torch.float32)
ytr = torch.tensor([FAIL[i] for i in tr], dtype=torch.float32)
sv = torch.tensor([SAVE] * len(tr))
ld = torch.utils.data.DataLoader(torch.utils.data.TensorDataset(Xtr, ytr, sv), batch_size=64, shuffle=True)
head.train()
for ep in range(20):
    tot = 0.0
    for xb, yb, sb in ld:
        logits = head(xb)
        logp = torch.log_softmax(logits, dim=1)
        r_cheap, r_prem = sb - LAM_TRAIN * yb, torch.zeros_like(sb)
        R = torch.stack([r_cheap, r_prem], dim=1)
        base = R.mean(dim=1, keepdim=True)
        pg = -(torch.softmax(logits, dim=1) * (R - base) * logp).sum(dim=1).mean()
        cql = (torch.logsumexp(logits, dim=1) - logits.mean(dim=1)).mean() * 0.1
        loss = pg + cql
        opt.zero_grad()
        loss.backward()
        opt.step()
        tot += float(loss)
    if ep % 5 == 0:
        print(f"ep{ep} loss {tot / len(ld):.4f}")
torch.save(head.state_dict(), t / "bandit_head.pt")

head.eval()
ca = splits["calib"]
Xca = torch.tensor(np.stack([X[i] for i in ca]), dtype=torch.float32)
with torch.no_grad():
    p_bandit = torch.softmax(head(Xca), dim=1)[:, 0].numpy()
try:
    lr = pickle.load(open(t / "logreg.pkl", "rb"))
    p_lr = lr.predict_proba(np.stack([X[i] for i in ca]))[:, 1]
except Exception as e:  # noqa: BLE001
    print("logreg reuse failed, bandit only:", e)
    p_lr = p_bandit
score = 0.5 * p_bandit + 0.5 * p_lr
yca = np.array([FAIL[i] for i in ca])
out = []
for lam in [0.5, 1.0, 2.0, 5.0]:
    best = max(((float(((score < th).astype(float) * (SAVE - lam * yca)).mean()), float(th)) for th in [i / 200 for i in range(201)]))
    out.append({"lambda": lam, "thresh_reward_opt": round(best[1], 4), "mean_reward": round(best[0], 4)})
    print(out[-1])
(t / "DECISION_03.json").write_text(json.dumps(
    {"stage": "03_bandit", "lambdas": out, "frozen_head": "bandit_head.pt",
     "note": "NB04 picks conformal tau, not these reward-opt thresholds"}, indent=2), encoding="utf-8")
