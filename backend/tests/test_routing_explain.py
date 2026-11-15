"""Occlusion explanations are approximate and per-request; labels are authored fixtures."""
from __future__ import annotations

import pytest
from sklearn.ensemble import RandomForestClassifier

from gateway.features.routing.explain import (
    LANGUAGE_FEATURES,
    OCCLUSION_NOTE,
    occlusion_items,
)
from gateway.features.routing.features import MODEL_FEATURE_NAMES

ROWS = 120


def make_rows() -> list[list[float]]:
    """Continuous length column, one language flag and a rare binary marker."""
    rows = [[0.0] * len(MODEL_FEATURE_NAMES) for _ in range(ROWS)]
    for index in range(ROWS):
        rows[index][0] = index / ROWS          # char_length-like, 0.0 .. 0.99
        rows[index][6] = float((index // 2) % 2)  # lang_english
        rows[index][12] = float(index % 5 == 0)   # has_digits-like, 20% true
    return rows


def training_means(rows: list[list[float]]) -> dict[str, float]:
    return {
        name: sum(row[index] for row in rows) / ROWS
        for index, name in enumerate(MODEL_FEATURE_NAMES)
    }


def test_occlusion_contributions_equal_base_minus_occluded_score():
    rows = make_rows()
    labels = [int(row[0] > 0.4 and row[12] == 1) for row in rows]
    assert set(labels) == {0, 1}
    forest = RandomForestClassifier(n_estimators=25, max_depth=3, random_state=0)
    forest.fit(rows, labels)
    means = training_means(rows)

    for row_index in (45, 100):  # first is economy, second is stronger
        vector = list(rows[row_index])
        base, items = occlusion_items(forest, vector, means, "english")

        assert base == pytest.approx(forest.predict_proba([vector])[0][1], abs=1e-12)
        assert 1 <= len(items) <= 5
        assert items == sorted(
            items, key=lambda item: abs(item["contribution"]), reverse=True
        )
        for item in items:
            occluded = list(vector)
            index = MODEL_FEATURE_NAMES.index(item["feature"])
            occluded[index] = means[item["feature"]]
            expected = base - forest.predict_proba([occluded])[0][1]
            assert item["contribution"] == pytest.approx(expected, abs=1e-12)
            assert item["value"] == pytest.approx(vector[index])
            assert item["direction"] == (
                "toward_stronger" if expected > 0 else "toward_economy"
            )

        # The same request produces the same explanation every time.
        assert occlusion_items(forest, vector, means, "english") == (base, items)

    # Sign convention: occluding a low value with a high mean pushed economy;
    # occluding the rare marker that made the request stronger pushed stronger.
    _, low_items = occlusion_items(forest, rows[45], means, "english")
    low_length = next(item for item in low_items if item["feature"] == "char_length")
    assert low_length["direction"] == "toward_economy"
    assert low_length["contribution"] < 0

    _, high_items = occlusion_items(forest, rows[100], means, "english")
    high_digits = next(item for item in high_items if item["feature"] == "has_digits")
    assert high_digits["direction"] == "toward_stronger"
    assert high_digits["contribution"] > 0


def test_language_columns_collapse_into_one_item():
    rows = make_rows()
    labels = [int(row[6]) for row in rows]
    forest = RandomForestClassifier(n_estimators=15, max_depth=3, random_state=0)
    forest.fit(rows, labels)
    means = training_means(rows)
    vector = list(rows[6])  # lang_english = 1

    base, items = occlusion_items(forest, vector, means, "english")
    language = [item for item in items if item["feature"] == "language_group"]
    assert len(language) == 1
    assert language[0]["value"] == "english"
    assert language[0]["direction"] == "toward_stronger"
    assert not any(item["feature"] in LANGUAGE_FEATURES for item in items)

    occluded = list(vector)
    for index, name in enumerate(MODEL_FEATURE_NAMES):
        if name in LANGUAGE_FEATURES:
            occluded[index] = means[name]
    expected = base - forest.predict_proba([occluded])[0][1]
    assert language[0]["contribution"] == pytest.approx(expected, abs=1e-12)
    assert OCCLUSION_NOTE.startswith("Approximate: one-feature-at-a-time")
