import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from gateway.app import app
from gateway.core.providers import Generation, Provider
from gateway.features.cache import api as cache_api
from gateway.features.cache.settings import CacheSettings


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(cache_api, "get_settings", lambda: SimpleNamespace(
        database_path=tmp_path / "cache.sqlite3",
        cache_threshold=0.55,
        mode="demo",
        cheap_model="demo-cheap",
        api_base_url="",
        api_key="",
    ))
    monkeypatch.setattr(cache_api, "get_cache_settings", lambda: CacheSettings(ttl_seconds=60, max_entries=100))
    return TestClient(app)


def test_normalization_handles_case_punctuation_and_hinglish():
    assert cache_api.normalize("  LIBRARY,   Kitab! ") == "library kitab"
    assert cache_api.normalize("किताब, वापस?") == "किताब वापस"


def test_seed_is_repeatable_and_exact_lookup(client: TestClient):
    assert client.post("/api/v1/cache/seed").json()["added"] == 3
    assert client.post("/api/v1/cache/seed").json()["added"] == 0
    result = client.post("/api/v1/cache/lookup", json={"text": "HOW CAN I RENEW A LIBRARY BOOK!"}).json()
    assert result["hit"] is True
    assert result["match_type"] == "exact"
    assert result["similarity"] == 1.0
    assert result["source"] == "authored-demo"


def test_semantic_lookup_respects_similarity_threshold(client: TestClient):
    client.post("/api/v1/cache/seed")
    result = client.post("/api/v1/cache/lookup", json={"text": "How can I renew my library book please?"}).json()
    assert result["match_type"] == "semantic"
    assert result["matched_question"] == "How can I renew a library book?"
    assert result["similarity"] >= result["threshold"]
    assert "review" in result["note"].lower()


def test_hinglish_paraphrase_matches_authored_faq(client: TestClient):
    client.post("/api/v1/cache/seed")
    result = client.post("/api/v1/cache/lookup", json={"text": "library ki book renew kaise karu"}).json()
    assert result["match_type"] == "semantic"
    assert result["matched_question"] == "How can I renew a library book?"
    assert result["similarity"] >= result["threshold"]


def test_devanagari_hindi_paraphrase_matches_authored_faq(client: TestClient):
    client.post("/api/v1/cache/seed")
    result = client.post("/api/v1/cache/lookup", json={"text": "लाइब्रेरी की किताब रिन्यू कैसे करूं"}).json()
    assert result["match_type"] == "semantic"
    assert result["matched_question"] == "How can I renew a library book?"


def test_unrelated_hinglish_prompt_does_not_reuse_an_english_faq(client: TestClient):
    client.post("/api/v1/cache/seed")
    result = client.post("/api/v1/cache/lookup", json={"text": "mera phone recharge kab khatam hoga"}).json()
    assert result["hit"] is False
    assert result["match_type"] == "none"


def test_missing_local_embedding_model_keeps_offline_hash_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        cache_api,
        "get_cache_settings",
        lambda: CacheSettings(embedding_model_path=str(tmp_path / "not-installed")),
    )
    assert cache_api._build_embedder().backend == "hash"


def test_different_details_are_not_reused(client: TestClient):
    client.post("/api/v1/cache/seed")
    result = client.post("/api/v1/cache/lookup", json={"text": "Can I change my exam date because I missed the bus?"}).json()
    assert result["hit"] is False
    assert result["match_type"] == "none"
    assert result["answer"] is None


def test_cache_management_and_counters(client: TestClient):
    client.post("/api/v1/cache/seed")
    client.post("/api/v1/cache/lookup", json={"text": "How can I renew a library book?"})
    client.post("/api/v1/cache/lookup", json={"text": "Can I change my exam date?"})
    stats = client.get("/api/v1/cache/stats").json()
    assert {key: stats[key] for key in ("total_lookups", "exact_hits", "semantic_hits", "misses")} == {
        "total_lookups": 2, "exact_hits": 1, "semantic_hits": 0, "misses": 1,
    }

    item_id = client.get("/api/v1/cache/entries").json()["items"][0]["id"]
    assert client.delete(f"/api/v1/cache/entries/{item_id}").status_code == 200
    assert client.delete("/api/v1/cache/entries").json()["deleted"] == 2
    assert client.get("/api/v1/cache/entries").json()["items"] == []


def test_answer_endpoint_learns_fixture_and_reuses_it(client: TestClient):
    question = "Can you explain how to renew a library book online?"
    first = client.post("/api/v1/cache/answer", json={"text": question}).json()
    assert first["mode"] == "demo"
    assert first["answer_source"] == "library-renewal"
    assert first["cache"]["status"] == "miss"
    assert first["cache"]["stored"] is True
    assert first["cache"]["durable_backend"] == "sqlite"

    second = client.post("/api/v1/cache/answer", json={"text": question}).json()
    assert second["answer_source"] == "cache"
    assert second["cache"]["status"] == "hit"
    assert second["cache"]["match_type"] == "exact"
    assert client.get("/api/v1/cache/entries").json()["items"][0]["source"] == "authored-demo"


def test_demo_fallback_is_not_learned(client: TestClient):
    result = client.post("/api/v1/cache/answer", json={"text": "What is the air quality today?"}).json()
    assert result["answer_source"] == "fallback"
    assert result["cache"]["stored"] is False
    assert "generic demo fallback" in result["cache"]["store_reason"]
    assert client.get("/api/v1/cache/entries").json()["items"] == []


def test_private_prompt_is_not_learned(client: TestClient):
    result = client.post(
        "/api/v1/cache/answer",
        json={"text": "Campus Wi-Fi login is broken; contact me at student@example.edu"},
    ).json()
    assert result["answer_source"] == "wifi-support"
    assert result["cache"]["stored"] is False
    assert "private identifier" in result["cache"]["store_reason"]


def test_live_provider_answer_is_learned(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    cache_api.get_settings().mode = "live"

    async def generate(_provider: Provider, text: str, model: str) -> Generation:
        return Generation(text="General campus support answer.", model=model, mode="live", source="live")

    monkeypatch.setattr(Provider, "generate", generate)
    question = "How can I find the campus shuttle schedule?"
    first = client.post("/api/v1/cache/answer", json={"text": question}).json()
    assert first["mode"] == "live"
    assert first["cache"]["stored"] is True
    assert first["cache"]["ttl_seconds"] == 60
    assert client.get("/api/v1/cache/entries").json()["items"][0]["source"] == "live-provider"

    second = client.post("/api/v1/cache/answer", json={"text": question}).json()
    assert second["answer_source"] == "cache"
    assert second["cache"]["match_type"] == "exact"


def test_learned_answer_expires(client: TestClient):
    question = "Can you explain how to renew a library book online?"
    first = client.post("/api/v1/cache/answer", json={"text": question}).json()
    assert first["cache"]["stored"] is True
    with sqlite3.connect(cache_api.get_settings().database_path) as db:
        db.execute("update cache_entry_runtime set expires_at=?", ("2000-01-01T00:00:00+00:00",))
    assert client.get("/api/v1/cache/entries").json()["items"] == []


def test_cache_entries_and_lookups_are_isolated_by_scope(client: TestClient):
    alpha = {"X-Cache-Scope": "tenant-alpha"}
    beta = {"X-Cache-Scope": "tenant-beta"}
    assert client.post("/api/v1/cache/seed", headers=alpha).json()["added"] == 3
    assert client.get("/api/v1/cache/entries", headers=beta).json()["items"] == []

    alpha_hit = client.post(
        "/api/v1/cache/lookup", headers=alpha, json={"text": "How can I renew a library book?"}
    ).json()
    beta_miss = client.post(
        "/api/v1/cache/lookup", headers=beta, json={"text": "How can I renew a library book?"}
    ).json()
    assert alpha_hit["match_type"] == "exact"
    assert beta_miss["hit"] is False
    assert client.get("/api/v1/cache/stats", headers=alpha).json()["exact_hits"] == 1
    assert client.get("/api/v1/cache/stats", headers=beta).json()["misses"] == 1

