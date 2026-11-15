"""End-to-end integration and verification tests for the unified Token Optimiser gateway.

Verifies that all 4 features:
1. Compression (Tushar)
2. Routing (Rakesh)
3. Cache (Shivam)
4. Insights & Output Capping (Aman)
integrate smoothly together as a single unified system.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from gateway.app import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_unified_service_health(client):
    """Health check confirms all components are available and responsive."""
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "cheap_model" in data
    assert "strong_model" in data


def test_unified_feature_endpoints_accessible(client):
    """Verify that every feature's primary contract responds successfully."""
    # 1. Compression
    comp = client.get("/api/v1/compression/samples")
    assert comp.status_code == 200
    assert len(comp.json()["samples"]) >= 3

    # 2. Routing
    rout = client.get("/api/v1/routing/models")
    assert rout.status_code == 200
    assert "models" in rout.json()

    # 3. Cache
    cache_stats = client.get("/api/v1/cache/stats")
    assert cache_stats.status_code == 200
    assert "total_lookups" in cache_stats.json()

    # 4. Insights
    insights_sum = client.get("/api/v1/insights/summary")
    assert insights_sum.status_code == 200
    assert insights_sum.json()["total_requests"] >= 15


def test_unified_pipeline_end_to_end_flow(client):
    """Simulates the full end-to-end lifecycle of a query across all 4 pillars:
    Query -> Cache Lookup (miss) -> Compression -> Routing -> Output Cap & Cost -> Record in Store.
    """
    user_prompt = "Hello sir, please tell me how can I renew my library book online before due date?"

    # --- Step 1: Cache Lookup (Shivam) ---
    cache_res = client.post("/api/v1/cache/lookup", json={"text": user_prompt, "language": "en"})
    assert cache_res.status_code == 200
    cache_data = cache_res.json()
    assert "match_type" in cache_data

    # --- Step 2: Prompt Compression (Tushar) ---
    comp_res = client.post(
        "/api/v1/compression/analyze",
        json={"text": user_prompt, "method": "heuristic", "budget": 0.6},
    )
    assert comp_res.status_code == 200
    comp_data = comp_res.json()
    compressed_text = comp_data["compressed"]
    assert len(compressed_text) > 0
    assert comp_data["original_tokens"] >= comp_data["compressed_tokens"]

    # --- Step 3: Model Routing (Rakesh) ---
    route_res = client.post(
        "/api/v1/routing/predict",
        json={
            "text": user_prompt,
            "compressed_text": compressed_text,
            "policy": "balanced",
        },
    )
    assert route_res.status_code == 200
    route_data = route_res.json()
    assert route_data["selected_tier"] in {"cheap", "strong", "quality", "economy", "balanced"}
    selected_tier = "premium" if route_data["selected_tier"] in {"strong", "quality"} else "cheap"

    # --- Step 4: Output Capping & Length Prediction (Aman) ---
    length_res = client.post(
        "/api/v1/insights/predict-length",
        json={
            "input_tokens": comp_data["compressed_tokens"],
            "language": "en",
            "format_constraint": "3 bullets",
            "max_tokens": 40,
        },
    )
    assert length_res.status_code == 200
    predicted_tokens = length_res.json()["predicted_output_tokens"]
    assert predicted_tokens <= 40

    # --- Step 5: Financial Cost Calculation (Aman) ---
    cost_res = client.post(
        "/api/v1/insights/cost-estimate",
        json={
            "text": compressed_text,
            "estimated_output_tokens": int(predicted_tokens),
            "tier": selected_tier,
            "format_constraint": "3 bullets",
            "max_tokens_cap": 40,
        },
    )
    assert cost_res.status_code == 200
    cost_data = cost_res.json()
    assert cost_data["cost_usd"] > 0
    assert cost_data["output_tokens_saved"] >= 0

    # --- Step 6: Record in Shared Store & History Audit (Aman) ---
    record_res = client.post(
        "/api/v1/insights/record",
        json={
            "text": user_prompt,
            "language": "en",
            "result": {
                "compressed": True,
                "compressed_text": compressed_text,
                "route": selected_tier,
                "cache_hit": cache_data.get("match_type") in {"exact", "semantic"},
                "input_tokens": comp_data["compressed_tokens"],
                "output_tokens": int(predicted_tokens),
                "cost_usd": cost_data["cost_usd"],
                "format_constraint": "3 bullets",
                "max_tokens": 40,
            },
        },
    )
    assert record_res.status_code == 200
    assert record_res.json()["status"] == "recorded"

    # Verify that the recorded request shows up in history audit
    history_res = client.get("/api/v1/insights/history?limit=10")
    assert history_res.status_code == 200
    history_items = history_res.json()["items"]
    assert any(user_prompt in item["text"] for item in history_items)


def test_multilingual_pipeline_integration(client):
    """Verifies that English, Hinglish, and Hindi queries are handled across the whole gateway."""
    queries = [
        ("en", "How do I renew my library book online?"),
        ("hinglish", "Meri library book kaise renew karun?"),
        ("hi", "पुस्तकालय की किताब का नवीकरण कैसे करें?"),
    ]

    for lang, text in queries:
        # Tokenize comparison
        tok_res = client.post("/api/v1/insights/tokenize", json={"text": text})
        assert tok_res.status_code == 200
        assert tok_res.json()["items"][0]["tokens"] > 0

        # Routing prediction
        rout_res = client.post("/api/v1/routing/predict", json={"text": text, "policy": "economy"})
        assert rout_res.status_code == 200
        assert "selected_tier" in rout_res.json()

        # Output capping demo exists
        cap_res = client.get("/api/v1/insights/output-cap-demo")
        assert cap_res.status_code == 200
        assert len(cap_res.json()["samples"]) >= 3


def test_cache_seed_and_lookup_hit(client):
    """Verify that seeded FAQs trigger cache hits and return authored responses."""
    # Seed FAQs
    seed_res = client.post("/api/v1/cache/seed")
    assert seed_res.status_code in {200, 201}

    # Exact query lookup
    lookup_res = client.post(
        "/api/v1/cache/lookup",
        json={"text": "How can I renew a library book?", "language": "en"},
    )
    assert lookup_res.status_code == 200
    lookup_data = lookup_res.json()
    assert lookup_data["match_type"] in {"exact", "semantic"}
    assert "answer" in lookup_data
    assert len(lookup_data["answer"]) > 0


def test_output_capping_financial_leverage(client):
    """Verifies that capping output delivers major cost savings regardless of the selected route."""
    for tier in ["cheap", "premium"]:
        res_uncapped = client.post(
            "/api/v1/insights/cost-estimate",
            json={
                "text": "Campus Wi-Fi portal connection guidelines",
                "estimated_output_tokens": 120,
                "tier": tier,
            },
        ).json()

        res_capped = client.post(
            "/api/v1/insights/cost-estimate",
            json={
                "text": "Campus Wi-Fi portal connection guidelines",
                "estimated_output_tokens": 120,
                "tier": tier,
                "format_constraint": "3 bullets",
                "max_tokens_cap": 40,
            },
        ).json()

        assert res_capped["cost_usd"] < res_uncapped["cost_usd"]
        assert res_capped["cost_saved_usd"] > 0
        assert res_capped["output_tokens_saved"] > 0
