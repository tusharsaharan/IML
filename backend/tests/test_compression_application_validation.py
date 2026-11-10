"""Offline checks for the application matrix, private bundle and finite timers."""
from __future__ import annotations

import base64
import hashlib
import io
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts/compression_research"
sys.path.insert(0, str(SCRIPTS))

from application_matrix import check_result, run_matrix  # noqa: E402
from kaggle_pilot import authored_cases, verified_source_data  # noqa: E402
from launch_application_batch import build_source, snapshot  # noqa: E402
from overnight_monitor import (  # noqa: E402
    CHECK_COUNT, INTERVAL_SECONDS, due_slots, normalize_status, run_command, schedule, version_label,
)

from gateway.app import app  # noqa: E402
from gateway.features.compression.service import CompressionService  # noqa: E402


@pytest.mark.parametrize("method", ["heuristic", "crf"])
@pytest.mark.parametrize("budget", [0.1, 0.6, 1])
def test_application_checker_accepts_real_both_language_output(method, budget):
    service = CompressionService()
    for case in [authored_cases()[0], authored_cases()[6], authored_cases()[12], authored_cases()[18]]:
        body = service.analyze(case["text"], method, budget, case["phrases"])
        check_result(body, case["text"], method, budget, case["phrases"], service.counter)


def test_application_checker_rejects_fabricated_token_savings():
    service = CompressionService()
    body = service.analyze("yaar mera email user@example.com par bhejo", "crf", 0.6, ["yaar"])
    body["saved_tokens"] = 100
    with pytest.raises(AssertionError):
        check_result(body, body["original"], "crf", 0.6, ["yaar"], service.counter)


def test_small_matrix_is_offline_and_records_validation(tmp_path):
    with TestClient(app) as client:
        result = run_matrix(client, authored_cases()[:1], tmp_path, budgets=(0.6, 1))
    assert result["status"] == "passed"
    assert result["calls"] == 8
    assert result["validation_checks"] == 10
    assert result["integration_approved"] is False


def test_exactly_twenty_half_hour_timers():
    start = datetime(2026, 11, 10, tzinfo=timezone.utc)
    slots = [datetime.fromisoformat(value) for value in schedule(start)]
    assert CHECK_COUNT == len(slots) == 20
    assert INTERVAL_SECONDS == 1800
    assert slots[0] - start == timedelta(minutes=30)
    assert slots[-1] - start == timedelta(hours=10)
    assert all(later - earlier == timedelta(minutes=30) for earlier, later in zip(slots, slots[1:]))


def test_windows_second_precision_does_not_skip_fired_slot():
    start = datetime(2026, 11, 10, microsecond=700000, tzinfo=timezone.utc)
    times = schedule(start)
    fired = datetime.fromisoformat(times[0]).replace(microsecond=0)
    assert due_slots(times, fired) == [0]
    assert due_slots(times, fired - timedelta(minutes=1)) == []


@pytest.mark.parametrize("value, expected", [(0, "QUEUED"), (1, "RUNNING"), (2, "COMPLETE"),
                                             (3, "ERROR"), ("COMPLETE", "COMPLETE"), (99, "UNKNOWN")])
def test_kaggle_status_normalization(value, expected):
    assert normalize_status(value) == expected


def test_kaggle_version_is_pinned_using_api_label():
    assert version_label("1") == "v1"
    assert version_label("v2") == "v2"


def test_source_transfer_allows_only_exact_verified_newline_conversion():
    source = b"original code\nsecond line\n"
    imported = source.replace(b"\n", b"\r\n")
    expected = hashlib.sha256(imported).hexdigest()
    assert verified_source_data(source, expected, True) == imported
    assert verified_source_data(imported, expected, True) == imported
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        verified_source_data(b"changed code\nsecond line\n", expected, True)
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        verified_source_data(source, expected, False)


def test_timer_never_passes_kaggle_credentials_to_frontend_or_browser(tmp_path, monkeypatch):
    import subprocess

    monkeypatch.setenv("KAGGLE_API_TOKEN", "unit-test-not-a-real-token")
    seen = {}

    def fake_run(command, **kwargs):
        seen.update(kwargs["env"])
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = run_command(["frontend-test"], tmp_path, tmp_path / "test.log", 5)
    assert result["status"] == "passed"
    assert "KAGGLE_API_TOKEN" not in seen


def test_snapshot_does_not_contain_credentials_or_runtime_data():
    encoded, fingerprints = snapshot()
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(encoded))) as archive:
        names = archive.namelist()
    assert "backend/tests/test_compression_phrases.py" in names
    assert "backend/src/gateway/features/compression/service.py" in names
    assert not any(".env" in name or "runtime/" in name or "__pycache__" in name for name in names)
    assert set(names) == set(fingerprints["files"])
    source = build_source(encoded, fingerprints)
    compile(source, "application-batch.py", "exec")
    assert "KAGGLE_API_TOKEN" not in source
    assert "enable_gpu=True" not in source
