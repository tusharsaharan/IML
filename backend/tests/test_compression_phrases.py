"""Studio post-run literal checks, not Kaggle/model research validation."""
import hashlib
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from gateway.app import app
from gateway.features.compression.service import CompressionService, SAMPLES, get_service
from gateway.schemas import CompressResult, DropRecord


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda sample: sample["id"])
@pytest.mark.parametrize("method", ["heuristic", "crf"])
def test_empty_list_keeps_existing_execution(sample, method):
    service = get_service()
    default = service.analyze(sample["text"], method)
    empty = service.analyze(sample["text"], method, protected_phrases=[])
    assert {k: v for k, v in default.items() if k != "elapsed_ms"} == {
        k: v for k, v in empty.items() if k != "elapsed_ms"
    }
    assert default["protected_phrases"] == []
    assert default["phrase_checks"] == []
    assert default["compression_candidate"] is None
    assert not default["protection_fallback"]


@pytest.mark.parametrize("method", ["heuristic", "crf"])
def test_real_lost_phrase_retains_original_and_candidate(method):
    text = SAMPLES[0]["text"]
    baseline = get_service().analyze(text, method)
    assert "yaar" not in baseline["compressed"]
    result = get_service().analyze(text, method, protected_phrases=["yaar", "user@example.com"])
    assert result["method"] == "protection_fallback"
    assert result["requested_method"] == method
    assert result["compressed"] == text
    assert result["compressed_tokens"] == result["original_tokens"]
    assert result["saved_tokens"] == 0
    assert result["compression_ratio"] == 1
    assert not result["budget_met"]
    assert result["removed_spans"] == result["added_spans"] == result["drop_records"] == []
    candidate = result["compression_candidate"]
    for field in ("compressed", "method", "compressed_tokens", "removed_spans", "added_spans", "drop_records", "fallback_reason"):
        assert candidate[field] == baseline[field]
    assert not candidate["protected_preserved"]
    assert result["protected_preserved"]
    assert result["phrase_checks"][0] == {
        "text": "yaar", "source_occurrences": 1, "candidate_occurrences": 0,
        "output_occurrences": 1, "preserved_in_candidate": False, "preserved_in_output": True,
    }
    assert result["phrase_checks"][1]["preserved_in_candidate"]


@pytest.mark.parametrize("method", ["heuristic", "crf"])
def test_surviving_selection_does_not_change_output(method):
    text = SAMPLES[0]["text"]
    baseline = get_service().analyze(text, method)
    result = get_service().analyze(text, method, protected_phrases=["user@example.com"])
    assert result["compressed"] == baseline["compressed"]
    assert result["method"] == baseline["method"]
    assert result["saved_tokens"] == baseline["saved_tokens"]
    assert not result["protection_fallback"]
    assert result["phrase_checks"][0]["preserved_in_candidate"]


def test_guard_calls_compressor_once_with_unmodified_input(monkeypatch):
    service = CompressionService()
    compress = Mock(wraps=service.compressor.compress_heuristic)
    monkeypatch.setattr(service.compressor, "compress_heuristic", compress)
    text = "yaar matlab mera email user@example.com par bhejo na"
    result = service.analyze(text, protected_phrases=["yaar"])
    compress.assert_called_once_with(text)
    assert result["protection_fallback"]


def test_occurrence_loss_even_with_one_copy_remaining(monkeypatch):
    # Explicit QA-only candidate to exercise multiplicity, not a model result.
    service = CompressionService()
    text = "deadline deadline"
    candidate = CompressResult(original=text, compressed="deadline", method="heuristic",
                               drops=[DropRecord(token="deadline", category="qa", rule="injected test candidate")])
    monkeypatch.setattr(service.compressor, "compress_heuristic", Mock(return_value=candidate))
    result = service.analyze(text, protected_phrases=["deadline"])
    assert result["protection_fallback"]
    assert result["phrase_checks"][0]["source_occurrences"] == 2
    assert result["phrase_checks"][0]["candidate_occurrences"] == 1
    assert result["compressed"] == text
    assert result["compression_candidate"]["drop_records"][0]["category"] == "qa"
    assert result["drop_records"] == []


@pytest.mark.parametrize("method", ["heuristic", "crf"])
def test_unicode_literal_offsets_and_overlapping_selections(method):
    text = "🙂 मेरा wifi काम नहीं कर रहा"
    phrases = ["मेरा", "wifi", "wifi काम", "नहीं"]
    result = get_service().analyze(text, method, protected_phrases=phrases)
    selected = [span for span in result["protected_spans"] if span["kind"] == "user_phrase"]
    assert len(selected) == len(phrases)
    assert all(text[span["start"]:span["end"]] == span["text"] for span in selected)
    assert next(span["start"] for span in selected if span["text"] == "मेरा") == 2
    assert all(check["preserved_in_output"] for check in result["phrase_checks"])


def test_regex_metacharacters_and_spaces_are_literals():
    text = "yaar support a+b.* and  wifi  please"
    result = get_service().analyze(text, protected_phrases=["a+b.*", " wifi "])
    assert result["protected_phrases"] == ["a+b.*", " wifi "]
    assert all(check["preserved_in_output"] for check in result["phrase_checks"])
    assert all(text[span["start"]:span["end"]] == span["text"] for span in result["protected_spans"])


def test_duplicates_are_deduplicated_not_inferred_twice(client):
    response = client.post("/api/v1/compression/analyze", json={"text": "wifi wifi", "protected_phrases": ["wifi", "wifi"]})
    assert response.status_code == 200
    result = response.json()
    assert result["protected_phrases"] == ["wifi"]
    assert len(result["phrase_checks"]) == 1
    assert result["phrase_checks"][0]["source_occurrences"] == 2


@pytest.mark.parametrize("phrases", [[""], [" \t"], ["Wifi"], ["missing"], ["x" * 201], ["wifi"] * 21, [123], "wifi", None])
def test_invalid_selection_api_returns_422(client, phrases):
    response = client.post("/api/v1/compression/analyze", json={"text": "wifi " + "x" * 201, "protected_phrases": phrases})
    assert response.status_code == 422


def test_direct_service_validation_before_execution(monkeypatch):
    service = CompressionService()
    compress = Mock()
    monkeypatch.setattr(service.compressor, "compress_heuristic", compress)
    with pytest.raises(ValueError, match="not found exactly"):
        service.analyze("wifi", protected_phrases=["WiFi"])
    compress.assert_not_called()


def test_maximum_phrase_size_and_count_accepted(client):
    phrases = [str(index) + "x" * (200 - len(str(index))) for index in range(20)]
    response = client.post("/api/v1/compression/analyze", json={"text": " ".join(phrases), "protected_phrases": phrases})
    assert response.status_code == 200
    assert len(response.json()["phrase_checks"]) == 20


def test_100_percent_passthrough_still_checks_phrases(monkeypatch):
    service = CompressionService()
    compress = Mock()
    monkeypatch.setattr(service.compressor, "compress_heuristic", compress)
    result = service.analyze("yaar wifi", budget=1, protected_phrases=["yaar"])
    compress.assert_not_called()
    assert result["method"] == "passthrough"
    assert not result["protection_fallback"]
    assert result["phrase_checks"][0]["preserved_in_candidate"]


def test_model_fallback_remains_in_candidate(tmp_path):
    service = CompressionService(tmp_path / "missing.pkl")
    result = service.analyze(SAMPLES[0]["text"], "crf", protected_phrases=["yaar"])
    assert result["method"] == "protection_fallback"
    assert result["compression_candidate"]["method"] == "heuristic"
    assert "unavailable" in result["compression_candidate"]["fallback_reason"]


@pytest.mark.parametrize("text,kept,lost", [
    pytest.param(SAMPLES[0]["text"], "user@example.com", "yaar", id="hinglish-upstream-preset"),
    pytest.param(SAMPLES[1]["text"], "wifi", "like", id="english-upstream-preset"),
    # Authored local QA cases, not a research evaluation dataset.
    pytest.param("yaar basically mera wifi nahi chal raha, user@example.com par update bhejo na",
                 "nahi", "yaar", id="hinglish-negation-qa"),
    pytest.param("hello sir, never change user@example.com; just check the report",
                 "never", "hello", id="english-negation-qa"),
    pytest.param("yaar yaar mera wifi slow hai", "wifi", "yaar", id="hinglish-repeated-qa"),
    pytest.param("wifi is slow, like really slow, like painfully slow, fix it",
                 "wifi", "like", id="english-repeated-qa"),
])
@pytest.mark.parametrize("method", ["heuristic", "crf"])
def test_both_languages_through_api(client, text, kept, lost, method):
    payload = {"text": text, "method": method, "budget": 0.6}

    def run(**changes):
        response = client.post("/api/v1/compression/analyze", json={**payload, **changes})
        assert response.status_code == 200
        return response.json()

    baseline = run()
    assert baseline["compressed"].count(kept) >= text.count(kept)
    assert baseline["compressed"].count(lost) < text.count(lost)
    empty = run(protected_phrases=[])
    assert {key: value for key, value in empty.items() if key != "elapsed_ms"} == {
        key: value for key, value in baseline.items() if key != "elapsed_ms"
    }

    surviving = run(protected_phrases=[kept])
    assert surviving["compressed"] == baseline["compressed"]
    assert surviving["method"] == baseline["method"]
    assert not surviving["protection_fallback"]
    assert surviving["phrase_checks"][0]["preserved_in_candidate"]

    guarded = run(protected_phrases=[kept, lost])
    assert guarded["method"] == "protection_fallback"
    assert guarded["compressed"] == text
    assert guarded["saved_tokens"] == 0
    assert guarded["compressed_tokens"] == guarded["original_tokens"]
    assert guarded["removed_spans"] == guarded["drop_records"] == []
    for field in ("compressed", "method", "compressed_tokens", "fallback_reason", "drop_records"):
        assert guarded["compression_candidate"][field] == baseline[field]
    check = guarded["phrase_checks"][1]
    assert check["source_occurrences"] == text.count(lost)
    assert check["candidate_occurrences"] == baseline["compressed"].count(lost)
    assert not check["preserved_in_candidate"]
    assert check["preserved_in_output"]
    assert check["output_occurrences"] == text.count(lost)
    assert all(text[span["start"]:span["end"]] == span["text"] for span in guarded["protected_spans"])

    passthrough = run(budget=1, protected_phrases=[lost])
    assert passthrough["method"] == "passthrough"
    assert passthrough["compressed"] == text
    assert not passthrough["protection_fallback"]
    assert client.post("/api/v1/compression/analyze", json={
        **payload, "protected_phrases": [lost.upper()],
    }).status_code == 422


def test_research_dependencies_still_match_pinned_manifest():
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / "docs/source-manifest.json").read_text(encoding="utf-8"))
    rows = [row for row in manifest["files"] if row["destination"].startswith((
        "backend/src/gateway/modules/m2_compressor/", "backend/src/gateway/lexicons/",
        "backend/data/models/", "backend/data/tfidf/",
    )) or row["destination"] in {"backend/src/gateway/schemas.py", "backend/src/gateway/tokenizer.py"}]
    assert rows
    for row in rows:
        assert hashlib.sha256((root / row["destination"]).read_bytes()).hexdigest() == row["sha256"], row["destination"]
