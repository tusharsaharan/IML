"""Authored routing dataset checks; labels are fixtures, not measured model correctness."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

DATASET = Path(__file__).resolve().parents[1] / "data/fixtures/routing_prompts.jsonl"

REQUIRED_KEYS = {"id", "text", "label", "group", "rubric", "source"}
LABELS = {"economy", "stronger"}
GROUPS = {"english", "hinglish", "hindi", "mixed_script"}
TAGS = {"reasoning", "math", "code", "analysis", "nuance", "constraints",
        "smalltalk", "lookup", "translate", "rewrite", "format", "yes_no"}


def rows() -> list[dict]:
    return [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_schema_and_allowed_values():
    for row in rows():
        assert set(row) == REQUIRED_KEYS, row.get("id")
        assert isinstance(row["id"], str) and row["id"].strip(), row
        assert isinstance(row["text"], str) and row["text"].strip(), row["id"]
        assert row["label"] in LABELS, row["id"]
        assert row["group"] in GROUPS, row["id"]
        assert row["source"] == "authored", row["id"]
        assert isinstance(row["rubric"], list) and row["rubric"], row["id"]
        assert set(row["rubric"]) <= TAGS, row["id"]


def test_ids_are_unique():
    ids = Counter(row["id"] for row in rows())
    assert sorted(value for value in ids.values() if value > 1) == []


def test_texts_have_no_exact_duplicates():
    texts = Counter(" ".join(row["text"].lower().split()) for row in rows())
    assert sorted(text for text, value in texts.items() if value > 1) == []


def test_dataset_size_and_per_group_label_balance():
    dataset = rows()
    assert len(dataset) >= 250
    table = defaultdict(Counter)
    for row in dataset:
        table[row["group"]][row["label"]] += 1
    for group in GROUPS:
        assert table[group]["economy"] > 0 and table[group]["stronger"] > 0, group
        share = table[group]["stronger"] / (table[group]["economy"] + table[group]["stronger"])
        assert 0.30 <= share <= 0.65, (group, share)
