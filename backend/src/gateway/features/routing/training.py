"""Train and evaluate the authored-fixture routing classifiers (CPU scikit-learn).

Metrics measure how well the classifiers reproduce the authored routing labels.
They are not measured model answer quality, cost savings or provider behaviour.
"""
from __future__ import annotations

import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from gateway.features.routing.features import MODEL_FEATURE_NAMES, extract_features

BACKEND = Path(__file__).resolve().parents[4]
REPO_ROOT = BACKEND.parent

RANDOM_SEED = 42
LABEL_TO_INT = {"economy": 0, "stronger": 1}
MODEL_NAMES = ("logistic_regression", "random_forest", "mlp")
PRIMARY_DEFAULT = "logistic_regression"
CV_FOLDS = 5
TEST_SIZE = 0.2
POLICY_OFFSET = 0.15
THRESHOLD_BOUNDS = (0.05, 0.95)
# Keep the balanced threshold away from the bounds so both authored offsets
# stay ordered inside [0.05, 0.95] even for an extreme learned threshold.
BALANCED_BOUNDS = (0.20, 0.80)
METRIC_DIGITS = 4


def make_model(name: str, seed: int = RANDOM_SEED):
    """Build an unfitted model; seeds are fixed for reproducibility."""
    if name == "logistic_regression":
        return Pipeline([
            ("scaler", StandardScaler()),
            ("logistic_regression", LogisticRegression(max_iter=1000, random_state=seed)),
        ])
    if name == "random_forest":
        return RandomForestClassifier(n_estimators=100, max_depth=6, random_state=seed)
    if name == "mlp":
        return Pipeline([
            ("scaler", StandardScaler()),
            ("mlp", MLPClassifier(hidden_layer_sizes=(16,), max_iter=500, random_state=seed)),
        ])
    raise ValueError(f"Unknown model: {name!r}. Choose from {MODEL_NAMES}.")


def model_params(name: str, seed: int = RANDOM_SEED) -> dict:
    """Constructor parameters recorded in the metrics artifact."""
    if name == "logistic_regression":
        return {"scaler": "StandardScaler", "max_iter": 1000, "solver": "lbfgs", "random_state": seed}
    if name == "random_forest":
        return {"n_estimators": 100, "max_depth": 6, "random_state": seed}
    if name == "mlp":
        return {"scaler": "StandardScaler", "hidden_layer_sizes": [16], "max_iter": 500, "random_state": seed}
    raise ValueError(f"Unknown model: {name!r}. Choose from {MODEL_NAMES}.")


def load_rows(dataset_path: Path) -> list[dict]:
    rows = []
    for number, line in enumerate(Path(dataset_path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("label") not in LABEL_TO_INT:
            raise ValueError(f"Row {number} has unsupported label {row.get('label')!r}.")
        rows.append(row)
    if not rows:
        raise ValueError("Dataset contains no rows.")
    return rows


def build_matrix(rows: list[dict]) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Extract MODEL_FEATURE_NAMES features; labels 0 = economy, 1 = stronger."""
    matrix = np.asarray([extract_features(row["text"]).vector() for row in rows], dtype=float)
    labels = np.asarray([LABEL_TO_INT[row["label"]] for row in rows], dtype=int)
    return matrix, labels, [row["group"] for row in rows]


def choose_threshold(probabilities: np.ndarray, labels: np.ndarray) -> tuple[float, float]:
    """Maximise F1 for the stronger class; ties go to the value closest to 0.5."""
    candidates = np.unique(np.concatenate([probabilities, np.asarray([0.5])]))
    best_key, best_threshold, best_f1 = None, 0.5, 0.0
    for candidate in candidates:
        threshold = float(candidate)
        f1 = f1_score(labels, (probabilities >= threshold).astype(int), pos_label=1, zero_division=0)
        key = (float(f1), -abs(threshold - 0.5))
        if best_key is None or key > best_key:
            best_key, best_threshold, best_f1 = key, threshold, float(f1)
    return best_threshold, best_f1


def policy_thresholds(balanced: float) -> dict[str, dict]:
    """Authored offsets around the balanced threshold, clipped to [0.05, 0.95]."""
    balanced = float(np.clip(balanced, *BALANCED_BOUNDS))
    low, high = THRESHOLD_BOUNDS
    economy = round(float(np.clip(balanced + POLICY_OFFSET, low, high)), METRIC_DIGITS)
    quality = round(float(np.clip(balanced - POLICY_OFFSET, low, high)), METRIC_DIGITS)
    balanced = round(balanced, METRIC_DIGITS)
    offset = f"{POLICY_OFFSET:.2f}"
    return {
        "economy": {"threshold": economy,
                    "note": f"Authored policy offset: balanced + {offset}, clipped to [{low}, {high}]."},
        "balanced": {"threshold": balanced,
                     "note": "F1-maximising threshold from out-of-fold train probabilities "
                             "(authored labels), kept inside "
                             f"[{BALANCED_BOUNDS[0]}, {BALANCED_BOUNDS[1]}] so the policy offsets stay ordered."},
        "quality": {"threshold": quality,
                    "note": f"Authored policy offset: balanced - {offset}, clipped to [{low}, {high}]."},
    }


def _display_path(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return Path(path).as_posix()


def _feature_correlations(matrix: np.ndarray, labels: np.ndarray) -> list[tuple[str, float]]:
    """Point-biserial correlation per feature, for the leakage sanity check only."""
    values = []
    for index, name in enumerate(MODEL_FEATURE_NAMES):
        column = matrix[:, index]
        if column.std() == 0:
            values.append((name, 0.0))
        else:
            values.append((name, float(np.corrcoef(column, labels)[0, 1])))
    return sorted(values, key=lambda item: -abs(item[1]))


def _dataset_info(rows: list[dict], dataset_path: Path | None, train_rows: int, test_rows: int) -> dict:
    labels = [LABEL_TO_INT[row["label"]] for row in rows]
    group_counts: dict[str, int] = {}
    for row in rows:
        group_counts[row["group"]] = group_counts.get(row["group"], 0) + 1
    info = {
        "path": _display_path(dataset_path) if dataset_path is not None else None,
        "sha256": hashlib.sha256(Path(dataset_path).read_bytes()).hexdigest() if dataset_path is not None else None,
        "rows": len(rows),
        "train_rows": train_rows,
        "test_rows": test_rows,
        "class_counts": {"economy": int(sum(1 for label in labels if label == 0)),
                         "stronger": int(sum(1 for label in labels if label == 1))},
        "group_counts": group_counts,
        "label_source_note": "authored fixture labels, not measured model correctness",
    }
    return info


def train(rows: list[dict], artifact_dir: Path, *, dataset_path: Path | None = None,
          seed: int = RANDOM_SEED) -> dict:
    """Train, evaluate and persist the routing models. Deterministic for a fixed seed."""
    if len(rows) < 20:
        raise ValueError("Need at least 20 rows for a stratified split and 5-fold CV.")
    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    matrix, labels, groups = build_matrix(rows)
    stratify = [f"{label}:{group}" for label, group in zip(labels, groups)]
    train_split = train_test_split(matrix, labels, groups, test_size=TEST_SIZE,
                                   random_state=seed, stratify=stratify)
    x_train, x_test, y_train, y_test, _groups_train, groups_test = train_split

    folds = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=seed)
    cv_scores = {name: [] for name in MODEL_NAMES}
    out_of_fold = {name: np.zeros(len(y_train)) for name in MODEL_NAMES}
    for fit_index, valid_index in folds.split(x_train, y_train):
        for name in MODEL_NAMES:
            model = make_model(name, seed)
            model.fit(x_train[fit_index], y_train[fit_index])
            out_of_fold[name][valid_index] = model.predict_proba(x_train[valid_index])[:, 1]
            cv_scores[name].append(f1_score(y_train[valid_index], model.predict(x_train[valid_index]),
                                            pos_label=1, zero_division=0))
    cv_summary = {name: (float(np.mean(scores)), float(np.std(scores))) for name, scores in cv_scores.items()}

    primary = PRIMARY_DEFAULT
    best_cv = max(MODEL_NAMES, key=lambda name: cv_summary[name][0])
    if best_cv != PRIMARY_DEFAULT and cv_summary[best_cv][0] - cv_summary[PRIMARY_DEFAULT][0] >= 0.02:
        primary = best_cv

    fitted, models = {}, {}
    for name in MODEL_NAMES:
        model = make_model(name, seed)
        model.fit(x_train, y_train)
        fitted[name] = model
        predicted = model.predict(x_test)
        entry = {
            "accuracy": round(float(accuracy_score(y_test, predicted)), METRIC_DIGITS),
            "precision": round(float(precision_score(y_test, predicted, pos_label=1, zero_division=0)), METRIC_DIGITS),
            "recall": round(float(recall_score(y_test, predicted, pos_label=1, zero_division=0)), METRIC_DIGITS),
            "f1": round(float(f1_score(y_test, predicted, pos_label=1, zero_division=0)), METRIC_DIGITS),
            "confusion_matrix": confusion_matrix(y_test, predicted, labels=[0, 1]).tolist(),
            "support": {"economy": int((y_test == 0).sum()), "stronger": int((y_test == 1).sum()),
                        "total": int(len(y_test))},
            "cv_f1_mean": round(cv_summary[name][0], METRIC_DIGITS),
            "cv_f1_std": round(cv_summary[name][1], METRIC_DIGITS),
            "params": model_params(name, seed),
        }
        if name == "mlp":
            mlp = model.named_steps["mlp"]
            entry["converged"] = bool(mlp.n_iter_ < mlp.max_iter)
            entry["n_iter"] = int(mlp.n_iter_)
        models[name] = entry

    threshold, threshold_f1 = choose_threshold(out_of_fold[primary], y_train)
    policies = policy_thresholds(threshold)
    primary_predicted = fitted[primary].predict(x_test)
    per_group = {}
    for group in sorted(set(groups_test)):
        mask = np.asarray([value == group for value in groups_test])
        per_group[group] = {
            "accuracy": round(float(accuracy_score(y_test[mask], primary_predicted[mask])), METRIC_DIGITS),
            "support": int(mask.sum()),
        }

    notes = [
        "Routing labels are authored fixtures. Metrics show how well the classifiers reproduce those labels, "
        "not real model answer quality, routing savings or provider behaviour.",
        f"Dataset: {len(rows)} authored prompts; the held-out test set has {len(y_test)} rows, so metric "
        "uncertainty is high.",
        "Primary model is logistic regression because it is interpretable and powers the explanation panel."
        if primary == PRIMARY_DEFAULT else
        f"Primary model is {primary} because its cross-validation F1 clearly beat logistic regression by at "
        "least 0.02; logistic regression is also saved as an interpretable baseline.",
        f"Balanced threshold {policies['balanced']['threshold']} maximises out-of-fold F1 "
        f"({round(threshold_f1, METRIC_DIGITS)}) on the train split; ties go to the value closest to 0.5.",
        "Policy thresholds are authored offsets, not learned or certified values. "
        "score >= threshold routes to the stronger tier; score < threshold routes to economy.",
        "Per-group accuracy uses only the held-out test rows; several groups have very few rows "
        "(see per_group_accuracy support), so these values are indicative, not guarantees.",
        "No hyperparameters were tuned on the test set.",
    ]
    if not models["mlp"].get("converged", True):
        notes.append(f"MLP did not converge within 500 iterations (n_iter={models['mlp'].get('n_iter')}); "
                     "its test metrics may understate a longer training run.")
    suspicious = [name for name, entry in models.items() if entry["accuracy"] > 0.97]
    top_feature, top_correlation = _feature_correlations(matrix, labels)[0]
    if suspicious or abs(top_correlation) >= 0.9:
        notes.append(f"Leakage check: {', '.join(suspicious) or 'no model'} above 0.97 test accuracy; "
                     f"largest single-feature correlation with the stronger label is "
                     f"{top_feature} r={round(top_correlation, 3)}. Treat as a leakage warning, not a result.")

    metrics = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "random_seed": seed,
        "library_versions": {"python": platform.python_version(), "scikit-learn": sklearn.__version__,
                             "numpy": np.__version__, "joblib": joblib.__version__},
        "dataset": _dataset_info(rows, dataset_path, len(y_train), len(y_test)),
        "evaluation_method": {
            "labels": "0 = economy, 1 = stronger",
            "split": f"stratified by label x group, {int((1 - TEST_SIZE) * 100)}/{int(TEST_SIZE * 100)} "
                     f"train/test, random_state={seed}",
            "cv": f"stratified {CV_FOLDS}-fold on the 80% train split, per-fold F1 for the stronger class",
            "test": "held-out 20% test set; accuracy, precision, recall and F1 for the stronger class",
            "confusion_matrix": "rows are true labels, columns are predicted labels, order economy then stronger",
            "threshold": "out-of-fold predicted probabilities on the train split; maximise F1, ties to 0.5",
        },
        "feature_names": list(MODEL_FEATURE_NAMES),
        "models": models,
        "primary_model": primary,
        "threshold": {"value": round(threshold, METRIC_DIGITS),
                      "method": "out-of-fold train probabilities (5-fold), F1-maximising, ties closest to 0.5",
                      "out_of_fold_f1": round(threshold_f1, METRIC_DIGITS)},
        "policies": policies,
        "per_group_accuracy": per_group,
        "notes": notes,
    }

    for name, model in fitted.items():
        joblib.dump(model, artifact_dir / f"routing_{name}.joblib")
    scaler = fitted[PRIMARY_DEFAULT].named_steps["scaler"]
    logreg = fitted[PRIMARY_DEFAULT].named_steps["logistic_regression"]
    coefficients = {
        "feature_names": list(MODEL_FEATURE_NAMES),
        "coefficients": [round(float(value), 6) for value in logreg.coef_[0]],
        "intercept": round(float(logreg.intercept_[0]), 6),
        "scaler_mean": [round(float(value), 6) for value in scaler.mean_],
        "scaler_scale": [round(float(value), 6) for value in scaler.scale_],
        "positive_class": "stronger",
        "note": "Linear coefficients on standardised features; positive values push toward the stronger tier. "
                "They describe fit on authored labels and are not causal effects.",
    }
    (artifact_dir / "routing_logreg_coefficients.json").write_text(
        json.dumps(coefficients, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (artifact_dir / "routing_metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return metrics


def train_from_jsonl(dataset_path: Path, artifact_dir: Path, *, seed: int = RANDOM_SEED) -> dict:
    """Load the authored JSONL dataset and call train()."""
    dataset_path = Path(dataset_path)
    return train(load_rows(dataset_path), artifact_dir, dataset_path=dataset_path, seed=seed)
