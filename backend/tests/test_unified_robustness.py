"""Robustness, safety invariants, and stress test suites for the unified Token Optimiser gateway.

Verifies:
- Mathematical invariants (monotonicity of cost, token bounds, code-mix bounds).
- Entity and safety span preservation across the multi-stage pipeline.
- End-to-end cache lifecycle (insert, hit, invalidate, miss).
- Stress and sequential execution across diverse multilingual queries.
- Defensive error handling against malformed inputs and boundary values.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from gateway.app import app
from gateway.modules.m1_pipeline.hinglish import code_mix_ratio


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. Mathematical & Architectural Invariants
# ---------------------------------------------------------------------------

def test_cost_monotonicity_invariant(client):
    """Invariant: Premium tier cost MUST be strictly greater than Cheap tier cost
    for any prompt with non-zero input and output tokens.
    """
    sample_text = "How do I renew my library book before semester finals?"
    cheap_cost = client.post(
        "/api/v1/insights/cost-estimate",
        json={"text": sample_text, "estimated_output_tokens": 80, "tier": "cheap"},
    ).json()["cost_usd"]

    premium_cost = client.post(
        "/api/v1/insights/cost-estimate",
        json={"text": sample_text, "estimated_output_tokens": 80, "tier": "premium"},
    ).json()["cost_usd"]

    assert cheap_cost > 0.0
    assert premium_cost > cheap_cost, f"Premium ({premium_cost}) should exceed Cheap ({cheap_cost})"
    # Premium should be approximately 2x input and 2x output rate of cheap
    ratio = premium_cost / cheap_cost
    assert 1.8 <= ratio <= 2.2


@pytest.mark.parametrize("cap_limit", [15, 25, 50, 100, 200])
def test_output_capping_strict_ceiling_invariant(client, cap_limit):
    """Invariant: When max_tokens_cap=C is specified, effective output tokens MUST NEVER exceed C."""
    # Test through prediction model
    pred_res = client.post(
        "/api/v1/insights/predict-length",
        json={
            "input_tokens": 50,
            "language": "en",
            "format_constraint": "3 bullets",
            "max_tokens": cap_limit,
        },
    ).json()
    assert pred_res["predicted_output_tokens"] <= cap_limit

    # Test through cost estimator
    cost_res = client.post(
        "/api/v1/insights/cost-estimate",
        json={
            "text": "Explain all course grading criteria in full detail.",
            "estimated_output_tokens": 500,
            "tier": "cheap",
            "max_tokens_cap": cap_limit,
        },
    ).json()
    assert cost_res["estimated_output_tokens"] <= cap_limit


@pytest.mark.parametrize("budget", [0.2, 0.4, 0.6, 0.8, 1.0])
def test_compression_budget_monotonicity_invariant(client, budget):
    """Invariant: For any prompt and budget B <= 1.0, compressed tokens <= original tokens."""
    text = "Hello team, can you basically please inform me about the library fine and due date policies?"
    res = client.post(
        "/api/v1/compression/analyze",
        json={"text": text, "method": "heuristic", "budget": budget},
    ).json()

    assert res["compressed_tokens"] <= res["original_tokens"]
    assert len(res["compressed"]) <= len(res["original"])


@pytest.mark.parametrize("text,expected_range", [
    ("hello world this is pure english", (0.0, 0.1)),
    ("mera hostel ka wifi bilkul slow chal raha hai yaar", (0.5, 1.0)),
    ("ye assignment 2 submit kaise karein online portal par", (0.4, 0.9)),
    ("किताब वापस करने का क्या नियम है", (0.9, 1.0)),
])
def test_code_mix_ratio_bounds(text, expected_range):
    """Invariant: code_mix_ratio must always be bounded in [0.0, 1.0]."""
    score = code_mix_ratio(text)
    assert 0.0 <= score <= 1.0
    min_exp, max_exp = expected_range
    assert min_exp <= score <= max_exp, f"Expected {expected_range} for '{text}', got {score}"


# ---------------------------------------------------------------------------
# 2. Safety Spans & Entity Preservation Across Pipeline
# ---------------------------------------------------------------------------

def test_protected_entities_preserved_through_pipeline(client):
    """Safety Invariant: Critical literals (emails, URLs, currencies, numbers)
    must survive compression and pass cleanly into the routing and insights stages.
    """
    literal_email = "support@campus-library.edu"
    literal_url = "https://library.campus.ac.in/renew"
    literal_fee = "Rs. 250"
    prompt = f"Please contact {literal_email} or visit {literal_url} to pay your pending fine of {literal_fee}."

    # Stage 1: Compression must not drop protected spans
    comp_res = client.post(
        "/api/v1/compression/analyze",
        json={"text": prompt, "method": "heuristic", "budget": 0.5},
    ).json()

    assert literal_email in comp_res["compressed"]
    assert literal_url in comp_res["compressed"]
    assert literal_fee in comp_res["compressed"]

    # Stage 2: Router must handle text with preserved URLs/emails
    route_res = client.post(
        "/api/v1/routing/predict",
        json={"text": prompt, "compressed_text": comp_res["compressed"], "policy": "balanced"},
    )
    assert route_res.status_code == 200
    assert route_res.json()["selected_tier"] in {"cheap", "strong"}

    # Stage 3: Cost calculation with entities
    cost_res = client.post(
        "/api/v1/insights/cost-estimate",
        json={"text": comp_res["compressed"], "estimated_output_tokens": 50, "tier": "cheap"},
    )
    assert cost_res.status_code == 200
    assert cost_res.json()["cost_usd"] > 0


# ---------------------------------------------------------------------------
# 3. Dynamic Cache Lifecycle (Insert -> Exact Hit -> Invalidate -> Miss)
# ---------------------------------------------------------------------------

def test_cache_full_lifecycle(client):
    """Verifies that adding a cache entry makes it discoverable, and deleting it restores miss."""
    unique_question = "What is the specific testing deadline for Lab 99?"
    unique_answer = "Lab 99 must be submitted by Friday 11:59 PM to the testing portal."

    # Step 1: Ensure initial lookup is a miss / none
    init_lookup = client.post(
        "/api/v1/cache/lookup",
        json={"text": unique_question, "language": "en"},
    ).json()
    assert init_lookup["match_type"] in {"none", "miss"}
    assert init_lookup.get("hit") is not True

    # Step 2: Insert new entry
    add_res = client.post(
        "/api/v1/cache/entries",
        json={"question": unique_question, "answer": unique_answer, "language": "en"},
    )
    assert add_res.status_code == 201
    entry_id = add_res.json()["id"]

    # Step 3: Lookup must now return an EXACT match
    hit_lookup = client.post(
        "/api/v1/cache/lookup",
        json={"text": unique_question, "language": "en"},
    ).json()
    assert hit_lookup["match_type"] in {"exact", "semantic"}
    assert hit_lookup["answer"] == unique_answer

    # Step 4: Delete the entry
    del_res = client.delete(f"/api/v1/cache/entries/{entry_id}")
    assert del_res.status_code == 200

    # Step 5: Lookup must return miss again
    final_lookup = client.post(
        "/api/v1/cache/lookup",
        json={"text": unique_question, "language": "en"},
    ).json()
    assert final_lookup["match_type"] in {"none", "miss"}


# ---------------------------------------------------------------------------
# 4. Sequential Execution Stress Test (20 Diverse Queries)
# ---------------------------------------------------------------------------

def test_sequential_pipeline_stress_execution(client):
    """Stress test: Runs 20 diverse multilingual requests sequentially through the entire pipeline:
    Cache -> Compress -> Route -> Cap & Predict -> Cost -> Record.
    Verifies that SQLite store remains consistent and does not lock.
    """
    stress_prompts = [
        "How do I renew my library book online?",
        "Meri library book expire hone wali hai, kaise renew karun?",
        "पुस्तकालय की पुस्तक नवीकरण की समय सीमा क्या है?",
        "Campus Wi-Fi is disconnecting frequently in the library.",
        "Wi-Fi password change karne ka tareeqa batao please.",
        "वाई-फाई नेटवर्क से कैसे जुड़ें?",
        "Where is Assignment 2 submission link located?",
        "Assignment submit karne me error aa raha hai, please help.",
        "असाइनमेंट जमा करने का आखिरी दिन कब है?",
        "Can I get an extension for Assignment 2 due to illness?",
        "Late assignment submit karne par kitne marks katte hain?",
        "What are the office hours for the course instructor?",
        "Lab exam syllabus me kya kya topics cover honge?",
        "Is there negative marking in the final semester exam?",
        "Hostel mess fees refund policy kya hai?",
        "How to apply for an official transcript from university?",
        "Transcript online apply ho sakti hai ya offline jaana hoga?",
        "Sports complex timings and access rules for students.",
        "Gym registration form kaise fill karein?",
        "What is the date for the upcoming hackathon event?",
    ]

    initial_summary = client.get("/api/v1/insights/summary").json()
    initial_recorded = initial_summary["recorded_in_store"]

    for i, prompt in enumerate(stress_prompts):
        # 1. Cache
        c_res = client.post("/api/v1/cache/lookup", json={"text": prompt, "language": "auto"}).json()

        # 2. Compress
        comp_res = client.post(
            "/api/v1/compression/analyze",
            json={"text": prompt, "method": "heuristic", "budget": 0.6},
        ).json()

        # 3. Route
        policy = "economy" if i % 2 == 0 else "quality"
        route_res = client.post(
            "/api/v1/routing/predict",
            json={"text": prompt, "compressed_text": comp_res["compressed"], "policy": policy},
        ).json()

        # 4. Predict & Cap
        pred_res = client.post(
            "/api/v1/insights/predict-length",
            json={
                "input_tokens": comp_res["compressed_tokens"],
                "language": "en" if i % 3 == 0 else "hinglish" if i % 3 == 1 else "hi",
                "format_constraint": "3 bullets",
                "max_tokens": 40,
            },
        ).json()

        # 5. Cost
        cost_res = client.post(
            "/api/v1/insights/cost-estimate",
            json={
                "text": comp_res["compressed"],
                "estimated_output_tokens": 80,
                "tier": "cheap" if route_res["selected_tier"] == "cheap" else "premium",
                "format_constraint": "3 bullets",
                "max_tokens_cap": 40,
            },
        ).json()

        # 6. Record
        rec_res = client.post(
            "/api/v1/insights/record",
            json={
                "text": prompt,
                "language": "auto",
                "result": {
                    "compressed_tokens": comp_res["compressed_tokens"],
                    "output_tokens": pred_res["predicted_output_tokens"],
                    "route": route_res["selected_tier"],
                    "cost_usd": cost_res["cost_usd"],
                    "cache_hit": c_res.get("match_type") in {"exact", "semantic"},
                },
            },
        )
        assert rec_res.status_code == 200

    # Verify that exactly 20 new records were committed to SQLite
    final_summary = client.get("/api/v1/insights/summary").json()
    assert final_summary["recorded_in_store"] == initial_recorded + len(stress_prompts)


# ---------------------------------------------------------------------------
# 5. Defensive Boundary & Malformed Input Handling
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_payload", [
    {"text": ""},  # empty text rejected
    {"text": "   \n\t  "},  # whitespace-only
    {"text": "x" * 15000},  # exceeds max length
    {"text": "valid text", "budget": 0.05},  # budget below 0.1
    {"text": "valid text", "budget": 1.5},  # budget above 1.0
    {"text": "valid text", "method": "unsupported_magic"},
])
def test_compression_input_validation(client, bad_payload):
    """Ensures input errors fail early with HTTP 422 Unprocessable Entity."""
    res = client.post("/api/v1/compression/analyze", json=bad_payload)
    assert res.status_code == 422


@pytest.mark.parametrize("bad_policy", ["ultra_cheap", "random", "aggressive", ""])
def test_routing_invalid_policy_rejected(client, bad_policy):
    """Routing policy must strictly be economy, balanced, or quality."""
    res = client.post(
        "/api/v1/routing/predict",
        json={"text": "How do I renew books?", "policy": bad_policy},
    )
    assert res.status_code == 422


def test_cost_estimator_user_price_boundary_validation(client):
    """Negative prices must be rejected."""
    res = client.post(
        "/api/v1/insights/cost-estimate",
        json={"text": "Wi-Fi help", "user_input_price_per_1k": -0.05},
    )
    assert res.status_code == 422
