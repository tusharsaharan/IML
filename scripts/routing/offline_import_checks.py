"""Authored import/contract checks, not measured routing quality or certification."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import gateway
import pytest

from gateway.llm import BaseLLMClient
from gateway.modules.m3_conformal.conformal import ConformalCalibrator
from gateway.modules.m4_router.difficulty import DifficultyScorer
from gateway.modules.m4_router.learned_policy import LearnedScorer, load_thresholds
from gateway.modules.m4_router.router import CascadeRouter
from gateway.tokenizer import TokenCounter

REFERENCE = Path(__file__).resolve().parents[2] / "backend/scripts/reference/code_mixed_gateway_router/backend"


def test_import_uses_reference_not_application_gateway():
    assert Path(gateway.__file__).resolve() == REFERENCE / "src/gateway/__init__.py"


@pytest.mark.parametrize("text", ["", "Hello", "bhai kal chutti hai kya", "मेरे खाते का पैसा नहीं भेजना",
                                      "Never send user@example.com Rs. 250", "solve 3+5*2 equation"])
def test_missing_trained_artifacts_are_explicit_heuristic_fallback(text, tmp_path):
    scorer = LearnedScorer(tmp_path)
    assert scorer.backend == "heuristic"
    assert scorer.status()["proxy"] is True
    assert scorer.score(text) == DifficultyScorer().score(text)
    assert load_thresholds(tmp_path) == {}


def test_upstream_token_count_feature_is_word_count_not_reference_tokens():
    text = "user@example.com"
    assert DifficultyScorer().features(text).token_count == len(text.split()) == 1
    assert TokenCounter().count(text) > 1


def test_threshold_equality_routes_premium():
    calibrator = ConformalCalibrator()
    calibrator.threshold = 0.35
    assert calibrator.tier(0.349) == "cheap"
    assert calibrator.tier(0.35) == "premium"


@pytest.mark.asyncio
async def test_dry_run_flag_does_not_prevent_supplied_client_call():
    class RecordingClient(BaseLLMClient):
        async def chat(self, *args, **kwargs):
            raise RuntimeError("supplied client was called")

    calibrator = ConformalCalibrator()
    router = CascadeRouter(calibrator, RecordingClient(), RecordingClient(), dry_run=True)
    with pytest.raises(RuntimeError, match="supplied client was called"):
        await router.dispatch_query("hello", task_id="authored-dry-run-check")


def test_separate_experiment_calibrator_handles_empty_input():
    path = REFERENCE / "experiments/cascade_routing/scripts/conformal.py"
    spec = importlib.util.spec_from_file_location("reference_experiment_conformal", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    threshold, rows = module.calibrate([])
    assert threshold is None
    assert len(rows) == 200
    assert all(row["n"] == 0 for row in rows)
