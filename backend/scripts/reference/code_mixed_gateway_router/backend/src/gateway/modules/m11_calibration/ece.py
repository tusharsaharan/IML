from __future__ import annotations


def expected_calibration_error(
    scores: list[float],
    labels: list[bool],
    n_bins: int = 10,
) -> float:
    """ECE for the cascade's cheap-success predictor.

    Predicted success probability is 1 - score (score is failure proxy in [0,1]).
    Labels are cheap_success (True=success). Bins are uniform over predicted prob.
    """
    if not scores or not labels or len(scores) != len(labels):
        return 0.0
    n = len(scores)
    bins: list[list[tuple[float, bool]]] = [[] for _ in range(n_bins)]
    for s, lab in zip(scores, labels, strict=True):
        p = max(0.0, min(1.0, 1.0 - s))
        idx = min(n_bins - 1, int(p * n_bins))
        bins[idx].append((p, lab))
    ece = 0.0
    for b in bins:
        if not b:
            continue
        acc = sum(1 for _, lab in b if lab) / len(b)
        conf = sum(p for p, _ in b) / len(b)
        ece += abs(acc - conf) * (len(b) / n)
    return round(ece, 6)


def reliability_diagram(
    scores: list[float],
    labels: list[bool],
    n_bins: int = 10,
) -> list[dict]:
    if not scores or not labels or len(scores) != len(labels):
        return []
    bins: list[list[tuple[float, bool]]] = [[] for _ in range(n_bins)]
    for s, lab in zip(scores, labels, strict=True):
        p = max(0.0, min(1.0, 1.0 - s))
        idx = min(n_bins - 1, int(p * n_bins))
        bins[idx].append((p, lab))
    out: list[dict] = []
    for i, b in enumerate(bins):
        if not b:
            out.append({"bin": i, "accuracy": 0.0, "confidence": 0.0, "count": 0})
            continue
        acc = sum(1 for _, lab in b if lab) / len(b)
        conf = sum(p for p, _ in b) / len(b)
        out.append(
            {
                "bin": i,
                "accuracy": round(acc, 4),
                "confidence": round(conf, 4),
                "count": len(b),
            }
        )
    return out
