import json

import pytest
from fastapi.testclient import TestClient

from gateway.app import app
from gateway.features.compression import evidence as module
from gateway.features.compression.evidence import get_evidence
from gateway.features.compression.service import ROOT


def test_evidence_is_exact_projection_not_authored_metrics():
    raw = json.loads((ROOT / "data/compression_evidence/verified_review.json").read_text(encoding="utf-8"))
    evidence = get_evidence()
    assert evidence["kind"] == "historical_development_evaluation"
    for key in ["qa_records", "qa_items", "source_passages", "stress_texts", "stress_records"]:
        assert evidence[key] == raw[key]
    assert len(evidence["rows"]) == 16
    for row in evidence["rows"]:
        source = raw["metrics"][row["model"]][f"bqwen35b_span@{row['target']}"]
        assert row["candidate_accuracy"] == source["accuracy"]
        assert row["context_kept"] == source["mean_context_ratio"]
        assert row["invalid"] == source["invalid"]
        assert row["original_accuracy"] == raw["metrics"][row["model"]]["original"]["accuracy"]


def test_evidence_includes_failures_and_limits():
    evidence = get_evidence()
    assert "punctuation-only" in evidence["results_markdown"]
    assert "do not claim end-to-end speedup" in evidence["results_markdown"]
    assert "unadjusted" in evidence["interpretation"]
    assert "not rerun locally" in evidence["verification_scope"]
    assert TestClient(app).get("/api/v1/compression/evidence").status_code == 200


def test_evidence_tampering_fails_closed(tmp_path, monkeypatch):
    source = ROOT / "data/compression_evidence"
    destination = tmp_path / "data/compression_evidence"
    destination.mkdir(parents=True)
    for file in source.iterdir():
        (destination / file.name).write_bytes(file.read_bytes())
    (destination / "verified_review.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        get_evidence()
    assert TestClient(app).get("/api/v1/compression/evidence").status_code == 503
