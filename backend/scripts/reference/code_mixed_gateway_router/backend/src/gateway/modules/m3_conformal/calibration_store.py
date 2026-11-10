from __future__ import annotations

import json
from pathlib import Path

from gateway.schemas import CalibSample


def append_sample(
    path: Path,
    sample_id: str,
    nonconformity: float,
    cheap_success: bool,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = CalibSample(id=sample_id, nonconformity=round(float(nonconformity), 6), cheap_success=bool(cheap_success))
    with path.open("a", encoding="utf-8") as fh:
        fh.write(row.model_dump_json() + "\n")


def append_many(path: Path, samples: list[CalibSample]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for s in samples:
            fh.write(s.model_dump_json() + "\n")


def load_samples(path: Path) -> list[CalibSample]:
    if not path.exists():
        return []
    out: list[CalibSample] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(CalibSample.model_validate(json.loads(line)))
        except Exception:
            continue
    return out


def is_real(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        text = path.read_text(encoding="utf-8")
        # Honest check: at least one bench-derived sample (handle no-space JSON)
        return "bench-" in text
    except Exception:
        return False


def data_state(
    samples: list[CalibSample],
    live_threshold: int = 30,
) -> dict:
    """Tri-state honesty: how much of the calibration set is real traffic.

    Returns one of three states so the frontend can display:
      - "synthetic" : zero human-labelled rows (0 real)
      - "mixed"     : some but fewer than ``live_threshold`` real rows
      - "live"      : >= ``live_threshold`` real rows (conformal claim is grounded)
    """
    total = len(samples)
    real = sum(1 for s in samples if not s.synthetic)
    if real >= live_threshold:
        state = "live"
    elif real > 0:
        state = "mixed"
    else:
        state = "synthetic"
    return {
        "state": state,
        "real_n": real,
        "total_n": total,
        "live_threshold": live_threshold,
    }
