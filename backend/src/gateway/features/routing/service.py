"""Routing adapter: trained classifiers with policy thresholds, plus a labelled fallback.

Scores are stronger-class probabilities for authored fixture labels. They are not
measured model correctness, savings or provider billing. No network calls are made
and no API key is required.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import joblib

from gateway.core.config import ARTIFACTS, get_settings
from gateway.features.routing.features import RoutingFeatures, extract_features
from gateway.features.routing.training import MODEL_NAMES
from gateway.tokenizer import TokenCounter

POLICIES: tuple[str, ...] = ("economy", "balanced", "quality")
# Stub thresholds, kept only for the clearly labelled starter-heuristic fallback.
STUB_THRESHOLDS = {"economy": 0.7, "balanced": 0.5, "quality": 0.3}
METRICS_FILE = "routing_metrics.json"
REPO_ROOT = Path(__file__).resolve().parents[5]
TRAINED_NOTE = (
    "Trained routing classifiers scored this prompt locally on CPU. Scores are "
    "probabilities for authored fixture labels, not model answer quality, savings or "
    "provider billing. compressed_text counts are informational and are not used in scoring."
)
FALLBACK_NOTE = (
    "Starter heuristic in use: trained routing artifacts were missing or unreadable. "
    "Scores are illustrative and are not classifier outputs."
)


@dataclass(frozen=True)
class Bundle:
    models: dict
    metrics: dict
    primary: str
    thresholds: dict[str, float]
    metrics_path: Path


def artifact_path(name: str, artifacts_dir: Path | None = None) -> Path:
    """Resolve an artifact name and refuse paths that escape the artifacts directory."""
    base = (Path(artifacts_dir) if artifacts_dir is not None else ARTIFACTS).resolve()
    candidate = (base / name).resolve()
    if not candidate.is_relative_to(base):
        raise ValueError(f"Artifact path escapes {base}: {name!r}.")
    return candidate


def load_metrics_artifact(artifacts_dir: Path | None = None) -> dict:
    """Read the routing metrics artifact once per caller; raises if absent or invalid."""
    return json.loads(artifact_path(METRICS_FILE, artifacts_dir).read_text(encoding="utf-8"))


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _features_payload(features: RoutingFeatures) -> dict:
    """Keep the starter feature keys and add every extracted feature."""
    return {
        **features.as_dict(),
        "token_count": features.reference_token_count,
        "char_count": features.char_length,
        "word_count": features.word_count,
        "code_mix_ratio": features.code_mix_ratio,
        "language_group": features.language_group,
    }


def _selected_label(tier: str) -> str:
    settings = get_settings()
    return settings.strong_model if tier == "strong" else settings.cheap_model


def _explanation(features: RoutingFeatures, policy: str, score: float, threshold: float,
                 tier: str, *, proxy: bool) -> list[str]:
    score_label = "Heuristic score" if proxy else "Stronger-class probability"
    return [
        f"Language group {features.language_group}; {features.reference_token_count} reference "
        f"tokens ({features.tokenizer_backend}).",
        f"{score_label} {score:.3f} against the {policy} threshold {threshold:.3f}.",
        f"score {'>=' if tier == 'strong' else '<'} threshold, so the {tier} tier is selected.",
    ]


class RoutingService:
    def __init__(self, artifacts_dir: Path | None = None) -> None:
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir is not None else ARTIFACTS
        self.counter = TokenCounter()
        self.bundle, self.fallback_reason = self._load_bundle()

    def _load_bundle(self) -> tuple[Bundle | None, str | None]:
        try:
            metrics_path = artifact_path(METRICS_FILE, self.artifacts_dir)
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            models = {}
            for name in MODEL_NAMES:
                model = joblib.load(artifact_path(f"routing_{name}.joblib", self.artifacts_dir))
                if not hasattr(model, "predict_proba"):
                    raise ValueError(f"routing_{name}.joblib cannot score probabilities.")
                models[name] = model
            primary = str(metrics["primary_model"])
            if primary not in models:
                raise ValueError(f"Primary model {primary!r} has no saved artifact.")
            thresholds = {policy: float(metrics["policies"][policy]["threshold"])
                          for policy in POLICIES}
            if not all(0.0 <= value <= 1.0 for value in thresholds.values()):
                raise ValueError("Policy thresholds must lie in [0, 1].")
            return Bundle(models=models, metrics=metrics, primary=primary,
                          thresholds=thresholds, metrics_path=metrics_path), None
        except Exception as exc:  # Any load failure degrades to the labelled fallback.
            return None, (
                f"Trained routing artifact unavailable or invalid "
                f"({type(exc).__name__}). Using the starter heuristic."
            )

    def model_scores(self, features: RoutingFeatures) -> dict[str, float]:
        """Real stronger-class probability from each saved classifier."""
        if self.bundle is None:
            raise RuntimeError("Trained models are not loaded.")
        row = [features.vector()]
        return {
            name: float(model.predict_proba(row)[0][1])
            for name, model in self.bundle.models.items()
        }

    def predict(self, text: str, policy: str, compressed_text: str | None = None) -> dict:
        if policy not in POLICIES:
            raise ValueError(f"Choose one of: {', '.join(POLICIES)}.")
        if self.bundle is None:
            return self._fallback(text, policy, compressed_text)
        features = extract_features(text)
        scores = self.model_scores(features)
        threshold = self.bundle.thresholds[policy]
        score = scores[self.bundle.primary]
        tier = "strong" if score >= threshold else "cheap"
        response = {
            "selected_tier": tier,
            "selected_model_label": _selected_label(tier),
            "score": round(score, 4),
            "threshold": threshold,
            "policy": policy,
            "features": _features_payload(features),
            "model_scores": {name: round(value, 4) for name, value in scores.items()},
            "explanation": _explanation(features, policy, score, threshold, tier, proxy=False),
            "note": TRAINED_NOTE,
            "scorer": {
                "requested": "trained_logistic_regression",
                "actual": f"trained_{self.bundle.primary}",
                "proxy": False,
                "reason": (
                    f"Artifact primary model is {self.bundle.primary} (selected by the "
                    "cross-validation F1 rule); logistic regression is still fitted and saved "
                    "for the explanation panel."
                ),
            },
            "artifact": {
                "path": _display_path(self.bundle.metrics_path),
                "generated_at": self.bundle.metrics.get("generated_at"),
                "dataset_rows": self.bundle.metrics.get("dataset", {}).get("rows"),
            },
            "labels_are_authored": True,
            "reference_token_count": features.reference_token_count,
            "tokenizer_backend": features.tokenizer_backend,
        }
        if compressed_text is not None:
            response["compressed_token_count"] = self.counter.count(compressed_text)
        return response

    def _fallback(self, text: str, policy: str, compressed_text: str | None) -> dict:
        """Exact starter formula; only used when trained artifacts cannot be loaded."""
        scored_text = compressed_text or text
        features = extract_features(scored_text)
        score = min(1.0, 0.15 + features.code_mix_ratio * 0.45
                    + min(features.reference_token_count, 120) / 220)
        threshold = STUB_THRESHOLDS[policy]
        tier = "strong" if score >= threshold else "cheap"
        # Same three keys as the trained path so the response shape stays stable; the
        # proxy flag and note make clear these are not classifier outputs.
        scores = {
            "logistic_regression": min(1.0, score),
            "random_forest": min(1.0, score + 0.03),
            "mlp": max(0.0, score - 0.02),
        }
        response = {
            "selected_tier": tier,
            "selected_model_label": _selected_label(tier),
            "score": round(score, 4),
            "threshold": threshold,
            "policy": policy,
            "features": _features_payload(features),
            "model_scores": {name: round(value, 4) for name, value in scores.items()},
            "explanation": _explanation(features, policy, score, threshold, tier, proxy=True),
            "note": f"{FALLBACK_NOTE} {self.fallback_reason}",
            "scorer": {
                "requested": "trained_logistic_regression",
                "actual": "starter_heuristic",
                "proxy": True,
                "reason": self.fallback_reason,
            },
            "artifact": {"path": None, "generated_at": None, "dataset_rows": None},
            "labels_are_authored": True,
            "reference_token_count": features.reference_token_count,
            "tokenizer_backend": features.tokenizer_backend,
        }
        if compressed_text is not None:
            response["compressed_token_count"] = self.counter.count(compressed_text)
        return response


@lru_cache(maxsize=1)
def get_service() -> RoutingService:
    return RoutingService()
