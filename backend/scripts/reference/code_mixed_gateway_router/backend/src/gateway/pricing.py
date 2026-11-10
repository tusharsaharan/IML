"""Single source of truth for LLM pricing.

All cost calculations must import from here — never hardcode rates inline.
Update PRICING_DATE when rates change and keep FX in sync with config.
Token counts come from TokenCounter (tiktoken_cl100k_base if installed,
otherwise whitespace) — hence $/₹ are approximate; see tokenizer report.
"""

PRICING_DATE = "2026-08-28"
CHEAP_PER_1K_USD = 0.00006  # Groq llama-3.1-8b-instant
PREMIUM_PER_1K_USD = 0.0025  # OpenAI gpt-4o
FX_INR_PER_USD = 83.5


def estimate_cost_usd(prompt_tokens: int, completion_tokens: int, per_1k: float) -> float:
    return (prompt_tokens + completion_tokens) * per_1k / 1000.0


def savings_vs_premium(
    prompt_tokens: int,
    completion_tokens: int,
    tier: str,
    cheap_per_1k: float = CHEAP_PER_1K_USD,
    premium_per_1k: float = PREMIUM_PER_1K_USD,
) -> float:
    cheap = estimate_cost_usd(prompt_tokens, completion_tokens, cheap_per_1k)
    premium = estimate_cost_usd(prompt_tokens, completion_tokens, premium_per_1k)
    if tier == "cheap":
        return max(0.0, premium - cheap)
    return 0.0
