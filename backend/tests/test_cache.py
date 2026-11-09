from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from gateway.app import app
from gateway.features.cache import api as cache_api


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(cache_api, "get_settings", lambda: SimpleNamespace(database_path=tmp_path / "cache.sqlite3", cache_threshold=0.55))
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
    assert stats == {"total_lookups": 2, "exact_hits": 1, "semantic_hits": 0, "misses": 1}

    item_id = client.get("/api/v1/cache/entries").json()["items"][0]["id"]
    assert client.delete(f"/api/v1/cache/entries/{item_id}").status_code == 200
    assert client.delete("/api/v1/cache/entries").json()["deleted"] == 2
    assert client.get("/api/v1/cache/entries").json()["items"] == []

