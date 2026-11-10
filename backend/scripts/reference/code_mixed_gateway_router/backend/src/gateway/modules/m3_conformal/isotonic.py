"""Isotonic-regression calibration of difficulty scores (Phase 2).

Maps the heuristic difficulty score to a calibrated probability of cheap-tier
failure via PAVA isotonic regression (no sklearn dependency). This is the
"regression learning" for the routing threshold: after calibration, the
difficulty score is a real P(failure) estimate that the conformal layer
operates on, instead of a raw weighted-feature heuristic.

Also exposes miscalibration diagnostics (ECE-style, reusing m11 bins) so the
calibration quality is measurable, not assumed.
"""

from __future__ import annotations

import numpy as np


def pava_isotonic(x: list[float], y: list[float]) -> tuple[np.ndarray, np.ndarray]:
    """Fit non-decreasing isotonic regression y ~ x.

    Returns (sorted_x, fitted_y_on_sorted_x). Ties in x are pre-averaged.
    """
    xa = np.asarray(x, dtype=float)
    ya = np.asarray(y, dtype=float)
    if xa.size == 0:
        return xa, ya
    order = np.argsort(xa, kind="stable")
    xs = xa[order]
    ys = ya[order]

    # pre-average duplicate x values
    ux: list[float] = []
    uy: list[float] = []
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[j + 1] == xs[i]:
            j += 1
        ux.append(float(xs[i]))
        uy.append(float(np.mean(ys[i : j + 1])))
        i = j + 1

    # PAVA on (ux, uy)
    blocks: list[tuple[float, int]] = [(v, 1) for v in uy]
    k = 0
    while k < len(blocks) - 1:
        if blocks[k][0] > blocks[k + 1][0]:
            val = (blocks[k][0] * blocks[k][1] + blocks[k + 1][0] * blocks[k + 1][1]) / (
                blocks[k][1] + blocks[k + 1][1]
            )
            merged = (val, blocks[k][1] + blocks[k + 1][1])
            blocks[k : k + 2] = [merged]
            k = max(0, k - 1)
        else:
            k += 1
    fitted: list[float] = []
    for v, w in blocks:
        fitted.extend([v] * w)
    return np.asarray(ux, dtype=float), np.asarray(fitted, dtype=float)


class IsotonicCalibrator:
    """difficulty score -> calibrated P(cheap-tier failure)."""

    def __init__(self) -> None:
        self.x_: np.ndarray | None = None
        self.y_: np.ndarray | None = None
        self.fitted = False

    def fit(self, scores: list[float], failures: list[bool]) -> IsotonicCalibrator:
        xs, ys = pava_isotonic([float(s) for s in scores], [1.0 if f else 0.0 for f in failures])
        self.x_, self.y_ = xs, ys
        self.fitted = xs.size > 0
        return self

    def predict(self, score: float) -> float:
        """Calibrated P(failure) for a difficulty score (step interpolation)."""
        if not self.fitted or self.x_ is None or self.y_ is None or self.x_.size == 0:
            return float(min(1.0, max(0.0, score)))
        s = float(score)
        if s <= self.x_[0]:
            return float(self.y_[0])
        if s >= self.x_[-1]:
            return float(self.y_[-1])
        idx = int(np.searchsorted(self.x_, s, side="right") - 1)
        return float(self.y_[idx])

    def predict_batch(self, scores: list[float]) -> list[float]:
        return [self.predict(s) for s in scores]

    def ece(self, scores: list[float], failures: list[bool], n_bins: int = 10) -> float:
        """ECE of the calibrated probabilities against realized failures."""
        if not scores or not failures or len(scores) != len(failures):
            return 0.0
        from gateway.modules.m11_calibration.ece import expected_calibration_error

        # ece expects (failure-proxy scores, cheap_success labels); our
        # predicted probabilities are P(failure), so pass 1 - p as the
        # success predictor and cheap_success labels directly.
        probs = self.predict_batch(scores)
        return expected_calibration_error([1.0 - p for p in probs], list(failures), n_bins=n_bins)

    def calibration_curve(self, scores: list[float], failures: list[bool], n_bins: int = 10) -> list[dict]:
        from gateway.modules.m11_calibration.ece import reliability_diagram

        probs = self.predict_batch(scores)
        return reliability_diagram([1.0 - p for p in probs], list(failures), n_bins=n_bins)
