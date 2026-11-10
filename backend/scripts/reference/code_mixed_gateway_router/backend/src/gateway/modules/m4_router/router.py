from __future__ import annotations

import time

from gateway.llm import BaseLLMClient
from gateway.modules.m3_conformal.conformal import ConformalCalibrator
from gateway.modules.m4_router.difficulty import DifficultyScorer
from gateway.pricing import CHEAP_PER_1K_USD, PREMIUM_PER_1K_USD
from gateway.schemas import DispatchResult
from gateway.tokenizer import TokenCounter


class CascadeRouter:
    """Routes a compressed prompt to cheap (Groq open model) or premium (GPT-4o) tier
    using a conformally-calibrated difficulty threshold."""

    def __init__(
        self,
        calibrator: ConformalCalibrator,
        cheap_client: BaseLLMClient,
        premium_client: BaseLLMClient,
        scorer: DifficultyScorer | None = None,
        counter: TokenCounter | None = None,
        dry_run: bool = True,
        cheap_cost_per_1k: float = CHEAP_PER_1K_USD,
        premium_cost_per_1k: float = PREMIUM_PER_1K_USD,
    ) -> None:
        self.calibrator = calibrator
        self.cheap_client = cheap_client
        self.premium_client = premium_client
        self.scorer = scorer or DifficultyScorer(counter)
        self.counter = counter or TokenCounter()
        self.dry_run = dry_run
        self.cost_per_1k = {"cheap": cheap_cost_per_1k, "premium": premium_cost_per_1k}

    def _estimate_cost(self, tier: str, prompt_tokens: int, completion_tokens: int) -> float:
        rate = self.cost_per_1k[tier]
        return (prompt_tokens + completion_tokens) * rate / 1000.0

    async def dispatch_query(
        self, text: str, task_id: str | None = None, temperature: float = 0.0, max_tokens: int | None = None
    ) -> DispatchResult:
        task_id = task_id or f"cmg-{id(self):x}-{int(time.time() * 1e6)}"
        score = self.scorer.score(text)
        threshold = self.calibrator.threshold
        tier = "premium" if self.calibrator.route_premium(score) else "cheap"
        client = self.premium_client if tier == "premium" else self.cheap_client

        start = time.perf_counter()
        result = await client.chat([{"role": "user", "content": text}], temperature=temperature, max_tokens=max_tokens)
        latency_ms = (time.perf_counter() - start) * 1000.0

        prompt_tokens = self.counter.count(text)
        completion_tokens = result.usage.completion_tokens or self.counter.count(result.content)
        cost = self._estimate_cost(tier, prompt_tokens, completion_tokens)

        return DispatchResult(
            task_id=task_id,
            model_routed=result.model,
            score=score,
            threshold=threshold,
            tier=tier,
            response=result.content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_est_usd=round(cost, 8),
            latency_ms=round(latency_ms, 3),
            dry_run=self.dry_run,
        )