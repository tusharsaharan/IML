"""Train the CRF Hinglish compressor (offline).

Usage:
    python scripts/train_crf.py --data data/training/bootstrap_filtered.jsonl \\
        --model data/models/crf_compressor.pkl [--dev-frac 0.15] [--seed 7]

Splits data into train/dev, trains sklearn-crfsuite LBFGS, reports weighted
F1 on dev, and pickles the model.
"""

from __future__ import annotations

import argparse
import json
import pickle
import random
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT / "src"))

from gateway.modules.m2_compressor.crf_tagger import featurize  # noqa: E402
from gateway.modules.m2_compressor.tfidf import load_idf  # noqa: E402


def load_examples(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def train(
    examples: list[dict],
    idf_map: dict[str, float],
    dev_frac: float,
    seed: float,
    model_out: Path,
) -> dict:
    import sklearn_crfsuite
    from sklearn_crfsuite import metrics

    rng = random.Random(seed)
    idx = list(range(len(examples)))
    rng.shuffle(idx)
    n_dev = max(1, int(len(examples) * dev_frac))
    dev_idx = set(idx[:n_dev])

    train_ex = [ex for k, ex in enumerate(examples) if k not in dev_idx]
    dev_ex = [ex for k, ex in enumerate(examples) if k in dev_idx]

    X_train = [featurize(ex["tokens"], idf_map) for ex in train_ex]
    y_train = [ex["labels"] for ex in train_ex]
    X_dev = [featurize(ex["tokens"], idf_map) for ex in dev_ex]
    y_dev = [ex["labels"] for ex in dev_ex]

    crf = sklearn_crfsuite.CRF(
        algorithm="lbfgs",
        c1=0.1,
        c2=0.1,
        max_iterations=200,
        all_possible_transitions=True,
    )
    crf.fit(X_train, y_train)
    y_pred = crf.predict(X_dev)
    f1 = metrics.flat_f1_score(y_dev, y_pred, average="weighted")

    model_out.parent.mkdir(parents=True, exist_ok=True)
    with model_out.open("wb") as fh:
        pickle.dump(crf, fh)

    # Top transition/feature weights for auditability.
    top_trans = sorted(crf.transition_features_.items(), key=lambda kv: -abs(kv[1]))[:10]
    top_state = sorted(crf.state_features_.items(), key=lambda kv: -abs(kv[1]))[:10]
    return {
        "f1_weighted": round(float(f1), 4),
        "train_size": len(train_ex),
        "dev_size": len(dev_ex),
        "model_path": str(model_out),
        "top_transitions": [(str(k), round(float(v), 4)) for k, v in top_trans],
        "top_state_features": [(str(k), round(float(v), 4)) for k, v in top_state],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/training/bootstrap_filtered.jsonl")
    ap.add_argument("--model", default="data/models/crf_compressor.pkl")
    ap.add_argument("--idf", default="data/tfidf/hinglish_idf.json")
    ap.add_argument("--dev-frac", type=float, default=0.15)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    data_path = Path(args.data)
    if not data_path.is_absolute():
        data_path = BACKEND_ROOT / data_path
    idf_path = Path(args.idf)
    if not idf_path.is_absolute():
        idf_path = BACKEND_ROOT / idf_path
    model_out = Path(args.model)
    if not model_out.is_absolute():
        model_out = BACKEND_ROOT / model_out

    examples = load_examples(data_path)
    idf_map = load_idf(idf_path) if idf_path.exists() else {}
    report = train(examples, idf_map, args.dev_frac, args.seed, model_out)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
