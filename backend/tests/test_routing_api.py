"""Routing API contracts. Metrics and labels are authored fixtures, not model correctness."""
from __future__ import annotations

import json
import dataclasses
import math
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gateway.app import app
from gateway.features.routing import api as routing_api
from gateway.features.routing import service as routing_service
from gateway.features.routing.features import MODEL_FEATURE_NAMES, extract_features
from gateway.features.routing.service import RoutingService, get_service
from gateway.features.routing.training import MODEL_NAMES

client = TestClient(app)
PREDICT = "/api/v1/routing/predict"
DATASET = Path(__file__).resolve().parents[1] / "data/fixtures/routing_prompts.jsonl"
PROMPTS = [json.loads(line)["text"]
           for line in DATASET.read_text(encoding="utf-8").splitlines()[:20]]
CONTRACT_KEYS = {"selected_tier", "selected_model_label", "score", "threshold", "policy",
                 "features", "model_scores", "explanation", "explanation_detail", "note"}


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
    assert body["explanation_detail"]["method"] == "unavailable"
    assert body["explanation_detail"]["features"] == []


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


def test_default_primary_returns_per_request_occlusion():
    service = get_service()
    if service.bundle is None:
        pytest.skip("Trained routing artifacts are unavailable in this checkout.")
    if service.bundle.primary == "logistic_regression":
        pytest.skip("This checkout uses logistic regression as the primary model.")
    text = "Mujhe apni team ke liye ek meeting agenda banana hai jisme launch aur budget cover ho."
    body = predict(text)
    detail = body["explanation_detail"]

    assert detail["method"] == "occlusion_vs_training_mean"
    assert detail["model"] == service.bundle.primary
    assert detail["is_request_specific"] is True
    assert detail["note"] == (
        "Approximate: one-feature-at-a-time comparison against the training average. "
        "Labels are authored fixtures."
    )
    assert 0.0 <= detail["base_score"] <= 1.0
    live = service.model_scores(extract_features(text))[service.bundle.primary]
    assert detail["base_score"] == pytest.approx(live, abs=1e-9)
    assert 1 <= len(detail["items"]) <= 5
    for item in detail["items"]:
        assert set(item) == {"feature", "value", "contribution", "direction"}
        assert "importance" not in item
        assert item["direction"] in {"toward_stronger", "toward_economy"}
        assert item["direction"] == (
            "toward_stronger" if item["contribution"] > 0 else "toward_economy"
        )
    assert detail["items"] == sorted(
        detail["items"], key=lambda item: abs(item["contribution"]), reverse=True
    )
    assert not any(item["feature"].startswith("lang_") for item in detail["items"])

    # Repeat calls are deterministic.
    assert predict(text)["explanation_detail"] == detail


def test_logreg_contributions_reproduce_the_logit_and_probability(monkeypatch):
    service = get_service()
    if service.bundle is None:
        pytest.skip("Trained routing artifacts are unavailable in this checkout.")
    if service.bundle.coefficients is None:
        pytest.skip("Logistic-regression coefficients are unavailable in this checkout.")
    monkeypatch.setattr(service, "bundle",
                        dataclasses.replace(service.bundle, primary="logistic_regression"))
    text = "Compare two loan options with trade-offs and show the math."
    body = predict(text)
    detail = body["explanation_detail"]

    assert detail["method"] == "logistic_regression_contribution"
    assert detail["model"] == "logistic_regression"
    assert detail["is_request_specific"] is True
    assert detail["note"] == "Explains the logistic-regression score; labels are authored fixtures."
    assert 1 <= len(detail["features"]) <= 5
    assert detail["features"] == sorted(
        detail["features"], key=lambda row: abs(row["contribution"]), reverse=True
    )
    assert all(row["direction"] in {"toward_stronger", "toward_economy"}
               for row in detail["features"])

    reconstructed = (detail["bias"]
                     + sum(row["contribution"] for row in detail["features"])
                     + detail["other_contribution"])
    assert reconstructed == pytest.approx(detail["logit"], abs=1e-9)
    probability = 1 / (1 + math.exp(-detail["logit"]))
    assert probability == pytest.approx(detail["probability"], abs=1e-9)

    # sigmoid(bias + contributions) reproduces the reported probability and the
    # (4-decimal) top-level score, which is the Step 06 requirement.
    assert round(detail["probability"], 4) == body["score"]

    # The saved artifact stores 6-decimal coefficients, so it reproduces the live
    # sklearn probability to about 2e-6 rather than bit-for-bit.
    live = service.model_scores(extract_features(text))["logistic_regression"]
    assert detail["probability"] == pytest.approx(live, abs=1e-4)


def test_logreg_primary_without_coefficients_is_flagged_not_invented(monkeypatch):
    service = get_service()
    if service.bundle is None:
        pytest.skip("Trained routing artifacts are unavailable in this checkout.")
    monkeypatch.setattr(service, "bundle", dataclasses.replace(
        service.bundle,
        primary="logistic_regression",
        coefficients=None,
        coefficients_error="Coefficient artifact missing for test.",
    ))
    response = client.post(PREDICT, json={"text": "hello", "policy": "balanced"})
    assert response.status_code == 200
    detail = response.json()["explanation_detail"]
    assert detail["method"] == "unavailable"
    assert detail["features"] == []
    assert detail["is_request_specific"] is False
    assert "Coefficient artifact missing for test." in detail["reason"]


def test_primary_without_training_means_is_flagged_not_invented(monkeypatch):
    service = get_service()
    if service.bundle is None:
        pytest.skip("Trained routing artifacts are unavailable in this checkout.")
    if service.bundle.primary == "logistic_regression":
        pytest.skip("Logistic regression explains itself from its coefficients.")
    monkeypatch.setattr(service, "bundle", dataclasses.replace(
        service.bundle,
        coefficients=None,
        coefficients_error="Training means missing for test.",
    ))
    response = client.post(PREDICT, json={"text": "hello", "policy": "balanced"})
    assert response.status_code == 200
    detail = response.json()["explanation_detail"]
    assert detail["method"] == "unavailable"
    assert detail["features"] == []
    assert detail["is_request_specific"] is False
    assert "Training feature means are unavailable" in detail["reason"]
    assert "Training means missing for test." in detail["reason"]


def test_models_endpoint_returns_metrics_artifact():
    response = client.get("/api/v1/routing/models")
    assert response.status_code == 200
    body = response.json()
    assert {"schema_version", "dataset", "models", "primary_model", "policies", "notes"} <= set(body)
    assert set(body["models"]) == set(MODEL_NAMES)


def test_shipped_coefficient_artifact_matches_the_explanation_contract():
    path = (Path(__file__).resolve().parents[1]
            / "data/artifacts/routing_logreg_coefficients.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["feature_names"] == list(MODEL_FEATURE_NAMES)
    for key in ("coefficients", "scaler_mean", "scaler_scale"):
        assert len(data[key]) == len(MODEL_FEATURE_NAMES), key
        assert all(isinstance(value, (int, float)) and math.isfinite(value)
                   for value in data[key]), key
    assert all(scale != 0 for scale in data["scaler_scale"])
    assert isinstance(data["intercept"], (int, float)) and math.isfinite(data["intercept"])
    assert data["positive_class"] == "stronger"


def test_models_endpoint_404_when_artifact_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(routing_service, "ARTIFACTS", tmp_path)
    response = client.get("/api/v1/routing/models")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
