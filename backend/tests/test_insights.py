"""Tests for Aman's Token & Cost Insights feature."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from gateway.app import app
from gateway.features.insights.models import get_length_predictor, load_request_fixtures


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_tokenize_default_multilingual(client):
    response = client.post("/api/v1/insights/tokenize", json={})
    assert response.status_code == 200
    data = response.json()
    assert "backend" in data
    assert len(data["items"]) == 3
    labels = {item["label"] for item in data["items"]}
    assert labels == {"English", "Hinglish", "Hindi"}
    for item in data["items"]:
        assert item["tokens"] > 0
        assert item["chars"] > 0
        assert item["tokens_per_char"] > 0


def test_tokenize_custom_variants(client):
    response = client.post(
        "/api/v1/insights/tokenize",
        json={
            "variants": {
                "short": "hi",
                "longer": "kya campus me wifi chal raha hai laptop par?",
            }
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 2
    assert data["items"][1]["tokens"] > data["items"][0]["tokens"]
    assert data["items"][1]["code_mix_ratio"] > 0


def test_summary_aggregates(client):
    response = client.get("/api/v1/insights/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["total_requests"] >= 15
    assert "languages" in data
    assert "en" in data["languages"] or "hinglish" in data["languages"]
    assert data["avg_tokens_saved_by_capping"] > 0


def test_record_and_history(client):
    record_resp = client.post(
        "/api/v1/insights/record",
        json={
            "text": "How do I renew my library card? Keep it brief.",
            "language": "en",
            "result": {
                "route": "economy",
                "cache_hit": False,
                "compressed": False,
                "input_tokens": 11,
                "output_tokens": 25,
                "max_tokens": 30,
                "format_constraint": "brief",
            },
        },
    )
    assert record_resp.status_code == 200
    assert record_resp.json()["status"] == "recorded"

    history_resp = client.get("/api/v1/insights/history?limit=10")
    assert history_resp.status_code == 200
    h_data = history_resp.json()
    assert len(h_data["items"]) > 0
    first = h_data["items"][0]
    assert "input_tokens" in first
    assert "output_tokens" in first
    assert "language" in first


def test_cost_estimate_catalog_and_output_cap(client):
    # Unconstrained
    unconstrained = client.post(
        "/api/v1/insights/cost-estimate",
        json={
            "text": "How do I renew my library book online before the due date?",
            "estimated_output_tokens": 100,
            "tier": "cheap",
        },
    ).json()

    # Capped with 3 bullets format constraint
    capped = client.post(
        "/api/v1/insights/cost-estimate",
        json={
            "text": "How do I renew my library book online before the due date?",
            "estimated_output_tokens": 100,
            "tier": "cheap",
            "format_constraint": "3 bullets",
            "max_tokens_cap": 50,
        },
    ).json()

    assert capped["estimated_output_tokens"] < unconstrained["estimated_output_tokens"]
    assert capped["cost_usd"] < unconstrained["cost_usd"]
    assert capped["output_tokens_saved"] > 0
    assert capped["cost_saved_usd"] > 0
    assert capped["rates_source"] == "catalog_cheap"


def test_cost_estimate_user_supplied_rates(client):
    resp = client.post(
        "/api/v1/insights/cost-estimate",
        json={
            "text": "Campus Wi-Fi connectivity issue",
            "estimated_output_tokens": 50,
            "user_input_price_per_1k": 0.002,
            "user_output_price_per_1k": 0.006,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["rates_source"] == "user_supplied"
    assert data["in_rate_per_1k_usd"] == 0.002
    assert data["out_rate_per_1k_usd"] == 0.006


def test_output_cap_demo_samples(client):
    resp = client.get("/api/v1/insights/output-cap-demo")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["samples"]) >= 3
    sample = data["samples"][0]
    assert "base_prompt" in sample
    assert "strategies" in sample
    assert len(sample["strategies"]) >= 3

    unconstrained = next(s for s in sample["strategies"] if s["strategy_id"] == "unconstrained")
    capped = next(s for s in sample["strategies"] if s["strategy_id"] == "three_bullets")

    assert capped["output_tokens"] < unconstrained["output_tokens"]
    assert capped["tokens_saved"] > 0
    assert capped["percent_saved"] > 0


def test_clusters_pca_and_kmeans(client):
    resp = client.get("/api/v1/insights/clusters")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["points"]) >= 15
    assert len(data["clusters"]) >= 2
    assert len(data["explained_variance_ratio"]) == 2
    for pt in data["points"]:
        assert "pc1" in pt
        assert "pc2" in pt
        assert "cluster" in pt
        assert "language" in pt


def test_predict_length_ridge_regression(client):
    resp = client.post(
        "/api/v1/insights/predict-length",
        json={
            "input_tokens": 15,
            "language": "en",
            "format_constraint": "3 bullets",
            "max_tokens": 40,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "predicted_output_tokens" in data
    assert data["predicted_output_tokens"] <= 40
    assert "r2_score" in data
    assert "mae_tokens" in data
    assert "coefficients" in data


def test_fixtures_integrity():
    fixtures = load_request_fixtures()
    assert len(fixtures) >= 15
    predictor = get_length_predictor()
    assert predictor.sample_count >= 15
    assert predictor.mae >= 0.0

