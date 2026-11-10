from __future__ import annotations

import math
from collections.abc import Iterable

from gateway.schemas import CalibSample

_GRID_SIZE = 200

_DEFAULT_GROUPS = ("all",)


def _hoeffding_correction(grid: int, delta: float, n: int) -> float:
    return math.sqrt(math.log(grid / delta) / (2 * n)) if n else math.inf


def _fixed_sequence_threshold(
    scores: list[float],
    failures: list[bool],
    alpha: float,
    delta: float,
    grid: int = _GRID_SIZE,
) -> tuple[float, float, float]:
    """Fixed-sequence Learn-Then-Test (Angelopoulos et al., 2110.01052).

    The deferral rule 'route premium iff score >= tau' is monotone: raising
    tau routes more traffic to the cheap tier, so the cheap-tier failure risk
    R(tau) is non-decreasing in tau. The fixed sequence therefore tests
    H0: R(tau) <= alpha from tau = 0.0 (all premium, riskless) upward in
    increasing tau, stopping at the first rejection. The last accepted tau is
    the selection. Because the sequence is fixed in advance, no Bonferroni /
    log(m) penalty is paid — the selected threshold dominates the
    Hoeffding-Bonferroni bound at the same (alpha, delta, n).
    """
    n = len(scores)
    if n == 0:
        return 0.0, 0.0, 0.0
    accepted = 0.0
    risk_hat = 0.0
    bound = 0.0
    for i in range(grid + 1):
        tau = i / grid
        k = sum(1 for s, f in zip(scores, failures, strict=True) if s < tau and f)
        risk = k / n
        ub = _binomial_ub(n, k, delta)
        if ub <= alpha:
            accepted = tau
            risk_hat = risk
            bound = ub
        else:
            break
    return accepted, risk_hat, bound


def _binomial_ub(n: int, k: float, delta: float) -> float:
    """Clopper-Pearson-style upper bound via the beta quantile.

    ub = Beta^{-1}(1 - delta; k + 1, n - k) — an exact UCB for a binomial
    proportion. Falls back to the conservative Chernoff form for degenerate
    cases without scipy.
    """
    kk = max(0.0, min(float(n), k))
    try:
        from scipy.stats import beta as _beta

        return float(_beta.ppf(1.0 - delta, kk + 1.0, n - kk))
    except ImportError:
        pass
    except Exception:
        pass
    # Chernoff/Hoeffding fallback
    if n == 0:
        return math.inf
    phat = kk / n
    cor = math.sqrt(math.log(1.0 / delta) / (2.0 * n))
    return min(1.0, phat + cor)


class ConformalCalibrator:
    """Conformal risk control (CRC) + Learn-Then-Test for the cascade error rate.

    Chooses a difficulty threshold ``tau`` for a monotone deferral rule
    ``route to premium iff score >= tau`` so the *unconditional* error rate
    (queries routed to the cheap tier that would have been handled incorrectly)
    is bounded by ``alpha`` with confidence ``1 - delta``.

    Methods:
    - ``fixed_sequence`` (default): sequential LTT over a descending tau grid
      with exact binomial tests — no multiplicity penalty.
    - ``hoeffding``: Bonferroni-corrected Hoeffding UCB over the grid
      (R_hat + sqrt(log(m/delta)/2n)) — the original implementation, kept for
      comparison and continuity with the published sweep.

    Mondrian mode: when calibration samples carry strata labels in
    ``CalibSample.group`` (e.g. code-mix buckets), a separate threshold is
    fitted per group with Bonferroni correction across groups; each group then
    gets its own guarantee. Samples without a group label fall in "all".
    """

    def __init__(
        self,
        alpha: float = 0.05,
        delta: float = 0.05,
        method: str = "fixed_sequence",
    ) -> None:
        if method not in ("fixed_sequence", "hoeffding"):
            raise ValueError(f"unknown method: {method}")
        self.alpha = alpha
        self.delta = delta
        self.method = method
        self.threshold: float = 0.0
        self.n_calib: int = 0
        self.n_fail: int = 0
        self.risk_hat: float = 0.0
        self.risk_bound: float = 0.0
        self.samples: list[CalibSample] = []
        self.group_thresholds: dict[str, float] = {}
        self.group_risk_bounds: dict[str, float] = {}
        self.is_mondrian: bool = False

    # ------------------------------------------------------------------ core

    def _fit_all(self, rows: list[CalibSample], delta: float) -> None:
        scores = [s.nonconformity for s in rows]
        failures = [not s.cheap_success for s in rows]
        n = len(rows)
        if n == 0:
            self.threshold = 0.0
            return
        if self.method == "fixed_sequence":
            tau, risk, bound = _fixed_sequence_threshold(scores, failures, self.alpha, delta)
            self.threshold = tau
            self.risk_hat = risk
            self.risk_bound = bound
            return
        # hoeffding (original)
        correction = _hoeffding_correction(_GRID_SIZE, delta, n)
        best = 0.0
        for i in range(_GRID_SIZE + 1):
            tau = i / _GRID_SIZE
            risk = sum(1 for s, f in zip(scores, failures, strict=True) if s < tau and f) / n
            if risk + correction <= self.alpha:
                best = tau
        self.threshold = best
        self.risk_hat = sum(1 for s, f in zip(scores, failures, strict=True) if s < best and f) / n
        self.risk_bound = self.risk_hat + correction

    def calibrate(self, samples: Iterable[CalibSample]) -> ConformalCalibrator:
        rows = list(samples)
        self.samples = rows
        self.n_calib = len(rows)
        self.n_fail = sum(1 for s in rows if not s.cheap_success)
        if self.n_calib == 0:
            self.threshold = 0.0
            self.group_thresholds = {}
            return self

        groups = {s.group for s in rows}
        # Mondrian only when there is more than one distinct stratum label
        mondrian = len(groups) > 1
        self.is_mondrian = mondrian

        if not mondrian:
            self._fit_all(rows, self.delta)
            self.group_thresholds = {}
            self.group_risk_bounds = {}
            return self

        # Bonferroni across G groups: each tested at delta/G
        n_groups = len(groups)
        delta_g = self.delta / n_groups
        self.group_thresholds = {}
        self.group_risk_bounds = {}
        for g in sorted(groups):
            sub = [s for s in rows if s.group == g]
            scores = [s.nonconformity for s in sub]
            failures = [not s.cheap_success for s in sub]
            n = len(sub)
            if n == 0:
                self.group_thresholds[g] = 0.0
                continue
            if self.method == "fixed_sequence":
                tau, _, bound = _fixed_sequence_threshold(scores, failures, self.alpha, delta_g)
            else:
                correction = _hoeffding_correction(_GRID_SIZE, delta_g, n)
                tau = 0.0
                best = 0.0
                for i in range(_GRID_SIZE + 1):
                    t = i / _GRID_SIZE
                    risk = sum(1 for s, f in zip(scores, failures, strict=True) if s < t and f) / n
                    if risk + correction <= self.alpha:
                        best = t
                tau = best
                bound = sum(1 for s, f in zip(scores, failures, strict=True) if s < best and f) / n + correction
            self.group_thresholds[g] = tau
            self.group_risk_bounds[g] = bound
        # global threshold = pooled fallback (used when group unknown)
        self._fit_all(rows, self.delta)
        # report the group-level guarantee as the (min) bound
        self.risk_bound = max(self.group_risk_bounds.values()) if self.group_risk_bounds else self.risk_bound
        return self

    # ------------------------------------------------------------------ query

    def sweep(self) -> list[dict]:
        """Evaluate R_hat(tau) and R_ub(tau) across the 200-point grid."""
        if self.n_calib == 0 or not self.samples:
            return []
        n_groups = len({s.group for s in self.samples})
        delta = self.delta / n_groups if n_groups > 1 else self.delta
        correction = _hoeffding_correction(_GRID_SIZE, delta, self.n_calib)
        points: list[dict] = []
        for i in range(_GRID_SIZE + 1):
            tau = round(i / _GRID_SIZE, 4)
            risk = sum(1 for s in self.samples if s.nonconformity < tau and not s.cheap_success) / self.n_calib
            bound = risk + correction
            points.append(
                {
                    "tau": tau,
                    "risk_hat": round(risk, 6),
                    "risk_bound": round(bound, 6),
                    "feasible": bound <= self.alpha,
                    "is_selected": abs(tau - self.threshold) < 1e-4,
                }
            )
        return points

    def sweep_by_group(self) -> dict[str, list[dict]]:
        """Per-group threshold sweeps (Mondrian visualization)."""
        out: dict[str, list[dict]] = {}
        if not self.samples:
            return out
        groups = sorted({s.group for s in self.samples})
        n_groups = len(groups)
        for g in groups:
            sub = [s for s in self.samples if s.group == g]
            n = len(sub)
            if n == 0:
                out[g] = []
                continue
            delta_g = self.delta / n_groups if n_groups > 1 else self.delta
            correction = _hoeffding_correction(_GRID_SIZE, delta_g, n)
            pts: list[dict] = []
            for i in range(_GRID_SIZE + 1):
                tau = round(i / _GRID_SIZE, 4)
                risk = sum(1 for s in sub if s.nonconformity < tau and not s.cheap_success) / n
                bound = risk + correction
                pts.append(
                    {
                        "tau": tau,
                        "risk_hat": round(risk, 6),
                        "risk_bound": round(bound, 6),
                        "feasible": bound <= self.alpha,
                        "is_selected": abs(tau - self.group_thresholds.get(g, 0.0)) < 1e-4,
                    }
                )
            out[g] = pts
        return out

    @classmethod
    def from_pairs(
        cls,
        scores: list[float],
        cheap_success: list[bool],
        alpha: float = 0.05,
        delta: float = 0.05,
        method: str = "fixed_sequence",
        groups: list[str] | None = None,
    ) -> ConformalCalibrator:
        samples = [
            CalibSample(
                id=str(i),
                nonconformity=s,
                cheap_success=ok,
                group=groups[i] if groups else "all",
            )
            for i, (s, ok) in enumerate(zip(scores, cheap_success, strict=True))
        ]
        return cls(alpha=alpha, delta=delta, method=method).calibrate(samples)

    def route_premium(self, score: float, group: str | None = None) -> bool:
        if group is not None and self.is_mondrian and group in self.group_thresholds:
            return score >= self.group_thresholds[group]
        return score >= self.threshold

    def tier(self, score: float, group: str | None = None) -> str:
        return "premium" if self.route_premium(score, group) else "cheap"

    # ------------------------------------------------------------------ alpha sweep

    def alpha_sweep(
        self,
        alphas: Iterable[float] | None = None,
        cheap_share: float | None = None,
    ) -> dict:
        """Sweep alpha (the SLA error budget) → threshold / coverage / savings.

        The 'sweet spot' answer for the 5% question: for each candidate alpha,
        refit the threshold on the same calibration set and report the
        (guaranteed) risk bound, realized risk, and premium-tier share (cost
        proxy). A knee (max curvature) on the alpha-vs-savings curve marks the
        point of diminishing returns, giving an evidence-based default alpha.

        ``cheap_share``: fraction of traffic routed cheap, per threshold, if
        provided by the caller (list aligned to alphas). Otherwise estimated
        from calibration nonconformity scores.
        """
        if not self.samples:
            return {"rows": [], "knee": None}
        if alphas is None:
            alphas = [0.01, 0.02, 0.03, 0.05, 0.075, 0.10, 0.15]
        # Sweep operates on pooled samples: one threshold per alpha with a
        # single consistent (threshold, realized risk, guaranteed bound)
        # triple. The Mondrian per-group view is exposed via sweep_by_group().
        pooled = [
            CalibSample(id=s.id, nonconformity=s.nonconformity, cheap_success=s.cheap_success, group="all")
            for s in self.samples
        ]
        rows: list[dict] = []
        for a in alphas:
            sub = ConformalCalibrator(alpha=a, delta=self.delta, method=self.method)
            sub.calibrate(pooled)
            n = self.n_calib
            cheap_n = sum(1 for s in pooled if s.nonconformity < sub.threshold)
            realized = sum(1 for s in pooled if s.nonconformity < sub.threshold and not s.cheap_success) / max(1, n)
            rows.append(
                {
                    "alpha": round(a, 4),
                    "threshold": round(sub.threshold, 4),
                    "risk_hat": round(realized, 4),
                    "risk_bound": round(min(1.0, sub.risk_bound), 4),
                    "cheap_share": round(cheap_n / max(1, n), 4),
                }
            )
        knee = _knee_detection([r["alpha"] for r in rows], [r["cheap_share"] for r in rows])
        return {"rows": rows, "knee": knee}


def _knee_detection(x: list[float], y: list[float]) -> float | None:
    """Kneedle-style knee: max distance from the (x,y) chord (normalized)."""
    if len(x) < 3 or len(x) != len(y):
        return None
    xs, ys = x, y
    xmin, xmax = min(xs), max(xs)
    if xmax == xmin:
        return None
    ymin, ymax = min(ys), max(ys)
    yspan = ymax - ymin
    nx = [(v - xmin) / (xmax - xmin) for v in xs]
    ny = [(v - ymin) / (yspan or 1.0) for v in ys]
    best_i, best_d = 0, -1.0
    for i in range(len(nx)):
        t = nx[i]
        chord = ny[0] + t * (ny[-1] - ny[0])
        d = abs(ny[i] - chord)
        if d > best_d:
            best_d, best_i = d, i
    return xs[best_i] if best_d > 0 else None
