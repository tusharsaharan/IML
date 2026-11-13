"""Training contract on synthetic data. Real metrics only reproduce authored labels."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gateway.features.routing.features import MODEL_FEATURE_NAMES
from gateway.features.routing.training import train_from_jsonl

MODEL_NAMES = {"logistic_regression", "random_forest", "mlp"}
REQUIRED_KEYS = {"schema_version", "generated_at", "random_seed", "library_versions", "dataset",
                 "evaluation_method", "feature_names", "models", "primary_model", "threshold",
                 "policies", "per_group_accuracy", "notes"}


def write_dataset(path: Path, rows: int = 60) -> Path:
    """Small synthetic frame: 30 stronger / 30 economy across two groups."""
    lines = []
    for index in range(rows):
        stronger = index % 2 == 0
        group = "english" if index % 4 < 2 else "hinglish"
        text = (f"Prove that sqrt({index + 2}) is irrational, attempt {index}."
                if stronger else f"Say hello to person number {index}.")
        lines.append(json.dumps({"id": f"syn-{index:03d}", "text": text,
                                 "label": "stronger" if stronger else "economy",
                                 "group": group, "rubric": ["math"] if stronger else ["smalltalk"],
                                 "source": "authored"}))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    dataset = write_dataset(tmp_path_factory.mktemp("dataset") / "synthetic.jsonl")
    artifacts = tmp_path_factory.mktemp("artifacts")
    return dataset, artifacts, train_from_jsonl(dataset, artifacts)


def test_artifact_contract(trained):
    _dataset, artifacts, metrics = trained
    assert REQUIRED_KEYS <= set(metrics)
    assert metrics["schema_version"] == 1
    assert metrics["feature_names"] == list(MODEL_FEATURE_NAMES)
    assert set(metrics["models"]) == MODEL_NAMES
    assert metrics["dataset"]["label_source_note"] == "authored fixture labels, not measured model correctness"
    assert (artifacts / "routing_metrics.json").is_file()
    assert (artifacts / "routing_logreg_coefficients.json").is_file()
    for name in MODEL_NAMES:
        assert (artifacts / f"routing_{name}.joblib").is_file()
    saved = json.loads((artifacts / "routing_metrics.json").read_text(encoding="utf-8"))
    assert saved["feature_names"] == metrics["feature_names"]


def test_policies_are_ordered_quality_balanced_economy(trained):
    policies = trained[2]["policies"]
    assert set(policies) == {"economy", "balanced", "quality"}
    quality = policies["quality"]["threshold"]
    balanced = policies["balanced"]["threshold"]
    economy = policies["economy"]["threshold"]
    assert quality < balanced < economy
    assert 0.05 <= quality and economy <= 0.95


def test_confusion_matrix_sums_to_support(trained):
    for name, entry in trained[2]["models"].items():
        total = sum(sum(row) for row in entry["confusion_matrix"])
        assert total == entry["support"]["total"] == trained[2]["dataset"]["test_rows"], name


def test_same_seed_gives_same_metrics(trained, tmp_path):
    dataset = trained[0]
    first = train_from_jsonl(dataset, tmp_path / "first", seed=42)
    second = train_from_jsonl(dataset, tmp_path / "second", seed=42)
    first.pop("generated_at")
    second.pop("generated_at")
    assert first == second
