"""One-feature-at-a-time occlusion explanations for the primary routing model.

For each model feature the request value is replaced by its training mean and the
primary classifier is re-scored. The difference from the real request score is an
approximate contribution: positive pushed toward the stronger tier, negative
toward economy. This ignores feature interactions and the training average is not
a real prompt, so the result is explicitly labelled approximate.
"""
from __future__ import annotations

from gateway.features.routing.features import MODEL_FEATURE_NAMES

LANGUAGE_FEATURES: tuple[str, ...] = (
    "lang_english",
    "lang_hinglish",
    "lang_mixed_script",
    "lang_hindi",
)
EXPLANATION_TOP_N = 5
OCCLUSION_NOTE = (
    "Approximate: one-feature-at-a-time comparison against the training average. "
    "Labels are authored fixtures."
)


def _direction(contribution: float) -> str:
    return "toward_stronger" if contribution > 0 else "toward_economy"


def occlusion_items(model, vector, means: dict[str, float], language_group: str,
                    top_n: int = EXPLANATION_TOP_N) -> tuple[float, list[dict]]:
    """Score the request, then occlude one feature (or the language block) at a time."""
    row = [float(value) for value in vector]
    language_indexes = [index for index, name in enumerate(MODEL_FEATURE_NAMES)
                        if name in LANGUAGE_FEATURES]
    occluded_rows: list[list[float]] = []
    descriptors: list[tuple[str, float | str]] = []
    for index, name in enumerate(MODEL_FEATURE_NAMES):
        if name in LANGUAGE_FEATURES:
            continue
        occluded = list(row)
        occluded[index] = float(means[name])
        occluded_rows.append(occluded)
        descriptors.append((name, row[index]))
    occluded = list(row)
    for index in language_indexes:
        occluded[index] = float(means[MODEL_FEATURE_NAMES[index]])
    occluded_rows.append(occluded)
    descriptors.append(("language_group", language_group))

    # One batched call keeps /predict cheap while matching per-row predict_proba.
    probabilities = model.predict_proba([row, *occluded_rows])
    base_score = float(probabilities[0][1])
    items: list[dict] = []
    for (feature, value), probability in zip(descriptors, probabilities[1:]):
        contribution = base_score - float(probability[1])
        if abs(contribution) > 1e-12:
            items.append({
                "feature": feature,
                "value": value,
                "contribution": contribution,
                "direction": _direction(contribution),
            })
    ranked = sorted(items, key=lambda item: abs(item["contribution"]), reverse=True)[:top_n]
    return base_score, ranked
