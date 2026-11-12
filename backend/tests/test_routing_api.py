"""Routing API contracts. Metrics and labels are authored fixtures, not model correctness."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gateway.app import app
from gateway.features.routing import api as routing_api
from gateway.features.routing import service as routing_service
from gateway.features.routing.features import extract_features
from gateway.features.routing.service import RoutingService, get_service
from gateway.features.routing.training import MODEL_NAMES

client = TestClient(app)
PREDICT = "/api/v1/routing/predict"
DATASET = Path(__file__).resolve().parents[1] / "data/fixtures/routing_prompts.jsonl"
PROMPTS = [json.loads(line)["text"]
           for line in DATASET.read_text(encoding="utf-8").splitlines()[:20]]
CONTRACT_KEYS = {"selected_tier", "selected_model_label", "score", "threshold", "policy",
                 "features", "model_scores", "explanation", "note"}


def predict(text: str, policy: str = "balanced", compressed_text: str | None = None) -> dict:
    payload = {"text": text, "policy": policy}
    if compressed_text is not None:
        payload["compressed_text"] = compressed_text
    response = client.post(PREDICT, json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_policy_thresholds_are_ordered_and_strong_counts_are_non_decreasing():
    text = "Compare two loan options with trade-offs and show the math."
    thresholds = {policy: predict(text, policy)["threshold"]
                  for policy in ("economy", "balanced", "quality")}
    assert thresholds["quality"] < thresholds["balanced"] < thresholds["economy"]

    counts = {}
    for policy in ("economy", "balanced", "quality"):
        tiers = [predict(prompt, policy)["selected_tier"] for prompt in PROMPTS]
        counts[policy] = tiers.count("strong")
    assert counts["economy"] <= counts["balanced"] <= counts["quality"]


def test_score_equal_to_threshold_selects_strong(monkeypatch):
    service = get_service()
    if service.bundle is None:
        pytest.skip("Trained routing artifacts are unavailable in this checkout.")
    threshold = service.bundle.thresholds["balanced"]
    monkeypatch.setattr(service, "model_scores",
                        lambda features: {name: threshold for name in MODEL_NAMES})
    body = predict("A prompt that lands exactly on the policy threshold.")
    assert body["selected_tier"] == "strong"
    assert body["score"] == pytest.approx(threshold)

    monkeypatch.setattr(service, "model_scores",
                        lambda features: {name: threshold - 1e-6 for name in MODEL_NAMES})
    assert predict("Just below the threshold.")["selected_tier"] == "cheap"


def test_missing_artifact_falls_back_to_starter_heuristic(tmp_path, monkeypatch):
    monkeypatch.setattr(routing_service, "ARTIFACTS", tmp_path / "absent")
    monkeypatch.setattr(routing_api, "get_service", lambda: RoutingService())
    body = predict("bhai kal chutti hai kya")
    assert body["scorer"]["requested"] == "trained_model"
    assert body["scorer"]["actual"] == "starter_heuristic"
    assert body["scorer"]["proxy"] is True
    assert body["selected_tier"] in {"strong", "cheap"}
    assert "starter heuristic" in body["note"].lower()
    assert set(body["model_scores"]) == set(MODEL_NAMES)


def test_invalid_policy_is_rejected_with_422():
    response = client.post(PREDICT, json={"text": "hello", "policy": "premium"})
    assert response.status_code == 422
    assert "policy" in response.text.lower()


@pytest.mark.parametrize("text", [
    "मेरा wifi काम नहीं कर रहा",
    "bhai kal chutti hai kya",
    "   \n\t ",
    "",
])
def test_language_whitespace_and_empty_inputs(text):
    body = predict(text)
    expected = extract_features(text)
    assert body["features"]["language_group"] == expected.language_group
    assert body["features"]["word_count"] == expected.word_count
    assert 0.0 <= body["score"] <= 1.0


def test_model_scores_are_three_real_probabilities():
    body = predict("Write a short release note with three bullet points.")
    assert set(body["model_scores"]) == set(MODEL_NAMES)
    assert all(0.0 <= value <= 1.0 for value in body["model_scores"].values())


def test_trained_response_keeps_contract_and_adds_audit_fields():
    service = get_service()
    if service.bundle is None:
        pytest.skip("Trained routing artifacts are unavailable in this checkout.")
    body = predict("Summarise this multi-part contract and flag the risks.")
    assert CONTRACT_KEYS <= set(body)
    assert body["labels_are_authored"] is True
    assert body["scorer"]["proxy"] is False
    assert body["scorer"]["actual"] == f"trained_{service.bundle.primary}"
    assert body["scorer"]["requested"] == body["scorer"]["actual"]
    assert body["artifact"]["path"] == "backend/data/artifacts/routing_metrics.json"
    assert body["artifact"]["dataset_rows"] >= 1
    assert isinstance(body["explanation"], list) and 2 <= len(body["explanation"]) <= 3
    assert body["features"]["char_length"] == len("Summarise this multi-part contract and flag the risks.")


def test_compressed_text_is_informational_only():
    text = "Draft a two-line reply to a delayed refund complaint."
    plain = predict(text)
    with_compressed = predict(text, compressed_text="draft reply refund late")
    assert "compressed_token_count" not in plain
    assert with_compressed["compressed_token_count"] >= 1
    assert with_compressed["score"] == plain["score"]
    assert with_compressed["selected_tier"] == plain["selected_tier"]


def test_models_endpoint_returns_metrics_artifact():
    response = client.get("/api/v1/routing/models")
    assert response.status_code == 200
    body = response.json()
    assert {"schema_version", "dataset", "models", "primary_model", "policies", "notes"} <= set(body)
    assert set(body["models"]) == set(MODEL_NAMES)


def test_models_endpoint_404_when_artifact_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(routing_service, "ARTIFACTS", tmp_path)
    response = client.get("/api/v1/routing/models")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
