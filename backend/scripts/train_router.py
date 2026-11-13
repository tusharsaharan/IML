"""Train the routing classifiers and write metrics/model artifacts.

Run: .venv\\Scripts\\python.exe backend/scripts/train_router.py
CPU-only; no network access and no provider calls. Labels are authored fixtures.
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND / "src"))

from gateway.features.routing.training import train_from_jsonl  # noqa: E402

DATASET = BACKEND / "data/fixtures/routing_prompts.jsonl"
ARTIFACTS = BACKEND / "data/artifacts"


def main() -> None:
    metrics = train_from_jsonl(DATASET, ARTIFACTS)
    dataset = metrics["dataset"]
    print(f"Routing classifiers on {dataset['rows']} authored prompts "
          f"({dataset['train_rows']} train / {dataset['test_rows']} test)")
    print(f"{'model':<22}{'cv_f1':<18}{'test_acc':<10}{'test_f1':<9}{'stronger support'}")
    for name, entry in metrics["models"].items():
        cv = f"{entry['cv_f1_mean']:.3f} +/- {entry['cv_f1_std']:.3f}"
        print(f"{name:<22}{cv:<18}{entry['accuracy']:<10.3f}{entry['f1']:<9.3f}{entry['support']['stronger']}")
    policies = metrics["policies"]
    print(f"primary model: {metrics['primary_model']}")
    print(f"thresholds: quality {policies['quality']['threshold']} < "
          f"balanced {policies['balanced']['threshold']} < economy {policies['economy']['threshold']}")
    print(f"wrote {ARTIFACTS / 'routing_metrics.json'}")
    print("Labels are authored fixtures; these numbers are not model correctness or savings.")


if __name__ == "__main__":
    main()
