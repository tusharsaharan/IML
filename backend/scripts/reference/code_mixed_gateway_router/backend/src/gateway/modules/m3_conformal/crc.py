"""Conformal Risk Control for compression fidelity (Phase 2, novel).

Replaces the hard-coded ``reward < 0.85`` failure constant with a learned,
statistically-guaranteed aggressiveness level. Following Angelopoulos et al.,
"Conformal Risk Control" (2208.02814): for a monotone loss family
``lambda -> loss(lambda)`` (higher lambda = more aggressive compression =
higher fidelity loss), the CRC fixed point

    lambda_hat = sup { lambda : (n / (n + 1)) * R_hat(lambda) + 1 / (n + 1) <= alpha }

guarantees ``E[loss(lambda_hat)] <= alpha`` on exchangeable test data. The
0.85 threshold question ("is reward >= 0.85?") becomes "pick the most
aggressive compression whose *expected* fidelity loss stays within the
budget alpha" â€” with the same alpha that controls the router.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CRCSample:
    """Fidelity loss of one compression at one aggressiveness level."""

    lam: float  # aggressiveness in [0, 1] (kept-ratio complement)
    loss: float  # fidelity loss in [0, 1] (1 - reward)


@dataclass
class CRCResult:
    lam_hat: float
    alpha: float
    n: int
    risk_hat: float
    risk_bound: float
    feasible: bool
    monotone: bool
    per_lambda: list[dict] = field(default_factory=list)


class ConformalFidelityControl:
    """Calibrate the compression aggressiveness lambda under an alpha budget.

    ``samples``: observed (lambda, loss) pairs. Multiple losses per lambda are
    allowed (averaged). The empirical risk curve must be non-decreasing in
    lambda (monotone loss family â€” CRC requirement); non-monotonic inputs are
    isotonic-regularized (averaged violations) and flagged ``monotone=False``.
    """

    def __init__(self, alpha: float = 0.05) -> None:
        if not 0.0 < alpha < 1.0:
            raise ValueError("alpha must be in (0, 1)")
        self.alpha = alpha

    def calibrate(self, samples: list[CRCSample]) -> CRCResult:
        if not samples:
            return CRCResult(0.0, self.alpha, 0, 0.0, self.alpha, False, True)

        # average losses per lambda, sorted ascending
        buckets: dict[float, list[float]] = {}
        for s in samples:
            buckets.setdefault(round(float(s.lam), 6), []).append(float(s.loss))
        lams = sorted(buckets)
        risks = [sum(v) / len(v) for v in (buckets[lam] for lam in lams)]
        n_total = len(samples)

        # enforce/verify monotonicity (isotonic via pooling adjacent violators)
        risks_reg, monotone = _pava(risks)

        # CRC fixed point over the sorted grid
        lam_hat = 0.0
        risk_hat = 0.0
        n = n_total
        for lam, r in zip(lams, risks_reg, strict=True):
            bound = (n / (n + 1)) * r + 1 / (n + 1)
            if bound <= self.alpha:
                lam_hat = lam
                risk_hat = r
            else:
                break
        feasible = (n / (n + 1)) * risks_reg[0] + 1 / (n + 1) <= self.alpha
        bound_sel = (n / (n + 1)) * risk_hat + 1 / (n + 1)

        per_lambda = [
            {
                "lambda": lam,
                "risk_hat": round(rr, 6),
                "risk_bound": round((n / (n + 1)) * rr + 1 / (n + 1), 6),
                "feasible": (n / (n + 1)) * rr + 1 / (n + 1) <= self.alpha,
                "is_selected": abs(lam - lam_hat) < 1e-9,
            }
            for lam, rr in zip(lams, risks_reg, strict=True)
        ]
        return CRCResult(
            lam_hat=lam_hat,
            alpha=self.alpha,
            n=n,
            risk_hat=round(risk_hat, 6),
            risk_bound=round(bound_sel, 6),
            feasible=feasible,
            monotone=monotone,
            per_lambda=per_lambda,
        )

    def calibrate_from_rewards(
        self,
        lambdas: list[float],
        rewards: list[float],
    ) -> CRCResult:
        """Convenience: build CRCSamples from observed rewards (loss = 1 - reward)."""
        samples = [
            CRCSample(lam=lam, loss=max(0.0, min(1.0, 1.0 - r)))
            for lam, r in zip(lambdas, rewards, strict=True)
        ]
        return self.calibrate(samples)


def _pava(values: list[float]) -> tuple[list[float], bool]:
    """Pool-Adjacent-Violators isotonic regression (non-decreasing).

    Returns (regularized values, was_already_monotone).
    """
    monotone = all(a <= b + 1e-12 for a, b in zip(values, values[1:], strict=False))
    if monotone:
        return list(values), True

    # PAVA: repeatedly pool adjacent violators into weighted averages
    blocks: list[tuple[float, int]] = [(v, 1) for v in values]
    i = 0
    while i < len(blocks) - 1:
        if blocks[i][0] > blocks[i + 1][0]:
            v = (blocks[i][0] * blocks[i][1] + blocks[i + 1][0] * blocks[i + 1][1]) / (blocks[i][1] + blocks[i + 1][1])
            merged = (v, blocks[i][1] + blocks[i + 1][1])
            blocks[i : i + 2] = [merged]
            i = max(0, i - 1)
        else:
            i += 1
    out: list[float] = []
    for v, w in blocks:
        out.extend([v] * w)
    return out, False
