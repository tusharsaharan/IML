import pytest

from gateway.llm import MockLLMClient
from gateway.modules.m3_conformal.conformal import ConformalCalibrator
from gateway.modules.m4_router.difficulty import DifficultyScorer
from gateway.modules.m4_router.router import CascadeRouter
from gateway.tokenizer import TokenCounter


def test_difficulty_score_bounded_and_higher_for_math():
    scorer = DifficultyScorer(TokenCounter())
    easy = scorer.score("bhai kal chutti hai kya")
    hard = scorer.score("integration ka formula solve karo yahan 3+5*2 numerator solve karo")
    assert 0.0 <= easy <= 1.0
    assert hard > easy


def test_difficulty_code_mix_raises_score():
    scorer = DifficultyScorer(TokenCounter())
    en = scorer.score("solve this equation for x")
    code = scorer.score("ye equation solve karo x ke liye")
    assert code > en


@pytest.mark.asyncio
async def test_dispatch_routes_premium_and_cheap():
    counter = TokenCounter()
    cal = ConformalCalibrator(alpha=0.05)
    cal.threshold = 0.35
    router = CascadeRouter(
        calibrator=cal,
        cheap_client=MockLLMClient("cheap-model"),
        premium_client=MockLLMClient("premium-model"),
        scorer=DifficultyScorer(counter),
        counter=counter,
        dry_run=True,
    )
    easy = await router.dispatch_query("bhai kal chutti hai kya")
    assert easy.tier == "cheap"
    assert easy.model_routed == "cheap-model"

    hard = await router.dispatch_query(
        "\u092f\u0947 5*3+2 \u0915\u093e \u0939\u0932 \u0926\u094b"
    )
    assert hard.tier == "premium"
    assert hard.model_routed == "premium-model"
    assert hard.response
    assert hard.cost_est_usd >= 0.0