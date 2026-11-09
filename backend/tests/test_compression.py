"""Adapter regression checks. Prompts reuse the pinned upstream test suite.

These checks do not estimate semantic accuracy, provider cost or throughput.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gateway.app import app
from gateway.features.compression.service import CompressionService, SAMPLES, get_service


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda sample: sample["id"])
@pytest.mark.parametrize("method", ["heuristic", "crf"])
def test_real_method_output(client, sample, method):
    response = client.post("/api/v1/compression/analyze", json={"text": sample["text"], "method": method})
    assert response.status_code == 200
    data = response.json()
    assert data["compressed"].strip()
    assert data["requested_method"] == method
    assert data["method"] in {"heuristic", "crf"}
    assert not data["method"].startswith("starter")
    assert data["original_tokens"] == get_service().counter.count(sample["text"])
    assert data["compressed_tokens"] == get_service().counter.count(data["compressed"])
    assert data["compression_ratio"] == data["compressed_tokens"] / data["original_tokens"]
    assert data["token_counts_are_billing"] is False
    assert data["evidence_kind"] == "local_execution"
    assert "source_commit" in data


# Verbatim literal fragments covered by the upstream safety-span implementation.
@pytest.mark.parametrize("literal", [
    "user@example.com", "https://example.com/help", "Rs. 2,500", "`index out of range`",
    "[1, 2, 2, 3]", '"daily nest-change evidence"', "2x + 3 = 7",
    "```python\nx = 2\nprint(x)\n```", "+91 98765 43210",
])
@pytest.mark.parametrize("method", ["heuristic", "crf"])
def test_protected_literals_preserved(literal, method):
    text = f"yaar basically {literal} ko change mat karo"
    result = get_service().analyze(text, method)
    assert literal in result["compressed"]
    assert result["protected_preserved"]
    assert any(span["text"] == literal for span in result["protected_spans"])
    assert all(text[span["start"]:span["end"]] == span["text"] for span in result["protected_spans"])


@pytest.mark.parametrize("text,guard", [
    ("wifi nahi chal raha hai", "nahi"), ("assignment submit nahin hua", "nahin"),
    ("mat karo ye", "mat"), ("never do this again", "never"),
    ("phone charge nhi ho rha", "nhi"), ("wifi nai chal rha", "nai"),
    ("kya wifi chal raha hai", "kya"), ("kab tak deadline hai", "kab"),
])
def test_crf_surface_guards(text, guard):
    result = get_service().analyze(text, "crf")
    assert guard in result["compressed"].split()
    assert any(span["text"] == guard and span["preserved"] for span in result["protected_spans"])


def test_crf_really_predicts():
    result = get_service().analyze("yaar basically mera hostel ka wifi bahut slow chal raha hai", "crf")
    assert result["method"] == "crf"
    assert any(drop["category"] == "crf" for drop in result["drop_records"])
    assert "wifi" in result["compressed"] and "slow" in result["compressed"]


@pytest.mark.parametrize("text", ["hello", "help", "namaste", "nahi", "arre yaar basically toh um hmm"])
@pytest.mark.parametrize("method", ["heuristic", "crf"])
def test_nonempty_edge_cases(text, method):
    assert get_service().analyze(text, method)["compressed"].strip()


@pytest.mark.parametrize("payload", [
    {"text": ""}, {"text": "  \n "}, {"text": "x" * 12001},
    {"text": "wifi", "method": "invented"}, {"text": "wifi", "budget": 0.05},
    {"text": "wifi", "budget": 1.1},
])
def test_invalid_requests(client, payload):
    assert client.post("/api/v1/compression/analyze", json=payload).status_code == 422


def test_budget_not_fake_strength():
    text = SAMPLES[0]["text"]
    low = get_service().analyze(text, "heuristic", 0.1)
    high = get_service().analyze(text, "heuristic", 0.9)
    assert low["compressed"] == high["compressed"]
    assert not low["budget_met"]
    assert high["budget_met"]
    assert not low["budget_tunable"]
    original = get_service().analyze(text, "crf", 1)
    assert original["compressed"] == text
    assert original["method"] == "passthrough"
    assert original["removed_spans"] == []


def test_missing_model_honest_fallback(tmp_path):
    service = CompressionService(tmp_path / "missing.pkl")
    result = service.analyze(SAMPLES[0]["text"], "crf")
    assert result["method"] == "heuristic"
    assert result["fallback_reason"]


def test_untrusted_model_is_not_unpickled(tmp_path):
    path = tmp_path / "different.pkl"
    path.write_bytes(b"not the pinned model")
    result = CompressionService(path).analyze(SAMPLES[0]["text"], "crf")
    assert result["method"] == "heuristic"
    assert result["fallback_reason"]


def test_prediction_failure_honest_fallback(monkeypatch):
    service = CompressionService()

    def fail(_tokens):
        raise RuntimeError("test inference failure")

    monkeypatch.setattr(service.tagger, "predict", fail)
    result = service.analyze(SAMPLES[0]["text"], "crf")
    assert result["method"] == "heuristic"
    assert result["fallback_reason"]


def test_actual_removed_offsets_and_greeting_audit():
    text = "hello sir, mera form bharna hai"
    result = get_service().analyze(text)
    assert not result["compressed"].startswith("hello")
    assert result["removed_spans"]  # Upstream does not log greeting drops in this path.
    assert all(text[span["start"]:span["end"]] == span["text"] for span in result["removed_spans"])


def test_three_samples_and_six_comparisons(client):
    assert len(client.get("/api/v1/compression/samples").json()["samples"]) == 3
    response = client.get("/api/v1/compression/compare?budget=0.5")
    assert response.status_code == 200
    rows = response.json()["rows"]
    assert len(rows) == 6
    assert len({row["sample_id"] for row in rows}) == 3
    assert {row["requested_method"] for row in rows} == {"heuristic", "crf"}
    assert all("/backend/tests/" in row["sample_source_url"] for row in rows)
    assert client.get("/api/v1/compression/compare?budget=nan").status_code == 422


def test_reference_tokenizer_fallback_label(monkeypatch):
    service = CompressionService()
    monkeypatch.setattr(service.counter, "_enc", None)
    result = service.analyze("hello sir, mera form bharna hai")
    assert result["tokenizer"] == "whitespace"
    assert result["original_tokens"] == len(result["original"].split())
    assert result["token_counts_are_billing"] is False


def test_imported_model_fingerprint():
    assert get_service()._model_verified()
    assert Path(get_service().model_path).is_file()
