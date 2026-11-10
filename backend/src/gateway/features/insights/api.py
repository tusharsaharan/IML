from __future__ import annotations

import json
from collections import Counter
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from gateway.core.config import ROOT, get_settings
from gateway.core.store import Store
from gateway.modules.m1_pipeline.hinglish import code_mix_ratio
from gateway.pricing import (
    CHEAP_OUT_PER_1K_USD,
    CHEAP_PER_1K_USD,
    PREMIUM_OUT_PER_1K_USD,
    PREMIUM_PER_1K_USD,
    estimate_cost_usd,
)
from gateway.tokenizer import TokenCounter

from .models import analyze_clusters, load_request_fixtures, predict_output_length

router = APIRouter(prefix="/api/v1/insights", tags=["insights"])
counter = TokenCounter()

FIXTURES_DIR = ROOT / "backend" / "data" / "fixtures"
CAP_SAMPLES_FILE = FIXTURES_DIR / "insights_cap_samples.json"


def _load_cap_samples() -> list[dict[str, Any]]:
    if not CAP_SAMPLES_FILE.exists():
        return []
    try:
        return json.loads(CAP_SAMPLES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


# --- Request/Response Models ---


class TokenizeRequest(BaseModel):
    text: str = ""
    variants: dict[str, str] | None = None


class RecordRequest(BaseModel):
    text: str
    language: str = "en"
    result: dict[str, Any] = Field(default_factory=dict)


class CostEstimateRequest(BaseModel):
    text: str
    estimated_output_tokens: int = Field(default=60, ge=1, le=4096)
    tier: Literal["cheap", "premium"] = "cheap"
    user_input_price_per_1k: float | None = Field(default=None, ge=0.0)
    user_output_price_per_1k: float | None = Field(default=None, ge=0.0)
    max_tokens_cap: int | None = Field(default=None, ge=1, le=4096)
    format_constraint: str | None = None


class PredictLengthRequest(BaseModel):
    input_tokens: int = Field(default=15, ge=1, le=4096)
    language: Literal["en", "hinglish", "hi"] = "en"
    format_constraint: str | None = None
    max_tokens: int | None = Field(default=None, ge=1, le=4096)


# --- Endpoints ---


@router.post("/tokenize")
def tokenize(request: TokenizeRequest):
    """Compare token counts across languages or text variants using the reference tokenizer."""
    variants = request.variants
    if not variants:
        if not request.text:
            variants = {
                "English": "How do I renew my library book online before the due date?",
                "Hinglish": "Meri library book kaise renew hogi? Urgent hai batao.",
                "Hindi": "पुस्तकालय की किताब की नवीकरण प्रक्रिया क्या है?",
            }
        else:
            variants = {"input": request.text}

    items = []
    for label, text in variants.items():
        tokens = counter.count(text)
        chars = len(text)
        cmr = code_mix_ratio(text)
        items.append({
            "label": label,
            "text": text,
            "tokens": tokens,
            "chars": chars,
            "tokens_per_char": round(tokens / max(chars, 1), 3),
            "code_mix_ratio": round(cmr, 3),
        })

    return {
        "backend": counter.backend,
        "items": items,
        "note": "Reference tokenization for comparison. Provider billing usage may differ.",
    }


@router.get("/summary")
def summary():
    """Aggregate stats across SQLite store and authored fixture requests."""
    settings = get_settings()
    store_items = Store(settings.database_path).list_requests(200)
    fixture_items = load_request_fixtures()

    all_languages: list[str] = [i["language"] for i in store_items] + [i.get("language", "en") for i in fixture_items]
    languages_dist = dict(Counter(all_languages))

    all_texts = [i["text"] for i in store_items] + [i.get("text", "") for i in fixture_items]
    avg_code_mix = round(sum(code_mix_ratio(t) for t in all_texts) / len(all_texts), 4) if all_texts else 0.0

    # Output cap savings stats across fixtures
    capped_samples = _load_cap_samples()
    total_tokens_saved = 0
    sample_count = 0
    for sample in capped_samples:
        for strat in sample.get("strategies", []):
            if strat.get("strategy_id") != "unconstrained":
                total_tokens_saved += strat.get("tokens_saved", 0)
                sample_count += 1
    avg_tokens_saved = round(total_tokens_saved / max(sample_count, 1), 1)

    return {
        "total_requests": len(store_items) + len(fixture_items),
        "recorded_in_store": len(store_items),
        "fixture_requests": len(fixture_items),
        "languages": languages_dist,
        "average_code_mix": avg_code_mix,
        "avg_tokens_saved_by_capping": avg_tokens_saved,
        "tokenizer_backend": counter.backend,
        "note": "Summary aggregates both live recorded session requests and authored fixture baselines.",
    }


@router.post("/record")
def record(request: RecordRequest):
    """Store a pipeline result into the shared SQLite store."""
    settings = get_settings()
    store = Store(settings.database_path)
    rid = store.record_request(request.text, request.language, request.result)
    return {"id": rid, "status": "recorded", "language": request.language}


@router.get("/history")
def history(limit: int = 50):
    """Return recent request history from SQLite store combined with authored fixtures."""
    settings = get_settings()
    store_items = Store(settings.database_path).list_requests(limit)

    formatted: list[dict[str, Any]] = []

    # Format live store requests
    for item in store_items:
        res = item.get("result", {})
        inp_tokens = res.get("input_tokens") or counter.count(item.get("text", ""))
        out_tokens = res.get("output_tokens") or 50
        formatted.append({
            "id": f"store-{item['id']}",
            "created_at": item.get("created_at", ""),
            "text": item.get("text", ""),
            "language": item.get("language", "en"),
            "route": res.get("route", "economy"),
            "model": res.get("model", settings.cheap_model),
            "cache_hit": bool(res.get("cache_hit", False)),
            "compressed": bool(res.get("compressed", False)),
            "input_tokens": inp_tokens,
            "output_tokens": out_tokens,
            "max_tokens_set": res.get("max_tokens"),
            "format_constraint": res.get("format_constraint"),
            "cost_usd": res.get("cost_usd", estimate_cost_usd(inp_tokens, out_tokens, CHEAP_PER_1K_USD, CHEAP_OUT_PER_1K_USD)),
            "source": "store",
        })

    # Add fixture items
    fixtures = load_request_fixtures()
    for fix in fixtures:
        formatted.append({
            **fix,
            "source": "fixture",
        })

    return {
        "items": formatted[:limit],
        "total": len(formatted),
        "note": "History displays both stored runtime requests and curated demo fixtures.",
    }


@router.post("/cost-estimate")
def cost_estimate(request: CostEstimateRequest):
    """Estimate request and completion costs with clear separation of reference token counts,
    standard catalog rates, and user-supplied pricing assumptions.
    """
    input_tokens = counter.count(request.text)

    # Output tokens: if max_tokens_cap is set and lower than estimated, cap it
    effective_output_tokens = request.estimated_output_tokens
    if request.max_tokens_cap and request.max_tokens_cap < effective_output_tokens:
        effective_output_tokens = request.max_tokens_cap

    # If format constraint like 3 bullets or json is set, estimate realistic token drop
    format_discount = 1.0
    if request.format_constraint:
        fmt = request.format_constraint.lower()
        if "bullet" in fmt:
            format_discount = 0.5
        elif "json" in fmt:
            format_discount = 0.45
        elif "preamble" in fmt or "1 line" in fmt:
            format_discount = 0.35
    effective_output_tokens = max(10, int(effective_output_tokens * format_discount))

    # Rates
    if request.user_input_price_per_1k is not None and request.user_output_price_per_1k is not None:
        in_rate = request.user_input_price_per_1k
        out_rate = request.user_output_price_per_1k
        rates_source = "user_supplied"
    else:
        if request.tier == "premium":
            in_rate = PREMIUM_PER_1K_USD
            out_rate = PREMIUM_OUT_PER_1K_USD
        else:
            in_rate = CHEAP_PER_1K_USD
            out_rate = CHEAP_OUT_PER_1K_USD
        rates_source = f"catalog_{request.tier}"

    cost_usd = estimate_cost_usd(input_tokens, effective_output_tokens, in_rate, out_rate)
    unconstrained_cost_usd = estimate_cost_usd(input_tokens, request.estimated_output_tokens, in_rate, out_rate)
    cost_saved_usd = max(0.0, unconstrained_cost_usd - cost_usd)

    return {
        "input_tokens": input_tokens,
        "estimated_output_tokens": effective_output_tokens,
        "unconstrained_output_tokens": request.estimated_output_tokens,
        "output_tokens_saved": request.estimated_output_tokens - effective_output_tokens,
        "cost_usd": round(cost_usd, 8),
        "unconstrained_cost_usd": round(unconstrained_cost_usd, 8),
        "cost_saved_usd": round(cost_saved_usd, 8),
        "rates_source": rates_source,
        "in_rate_per_1k_usd": in_rate,
        "out_rate_per_1k_usd": out_rate,
        "tokenizer_backend": counter.backend,
        "note": "Reference token counts and estimated rates. Not an invoice or provider guarantee.",
    }


@router.get("/output-cap-demo")
def output_cap_demo():
    """Return authored output capping samples demonstrating the impact of length and format constraints."""
    samples = _load_cap_samples()
    if not samples:
        raise HTTPException(status_code=503, detail="Output capping samples fixture not found.")
    return {
        "kind": "authored_output_cap_evidence",
        "samples": samples,
        "supported_strategies": [
            "Hard Token Cap (max_tokens)",
            "Format constraint: '3 bullets'",
            "Format constraint: 'JSON only'",
            "Format constraint: 'no preamble'",
            "Combined: format constraint + max_tokens",
        ],
        "note": "Curated demonstration of Point 2: 'Cap the output'. Compares token reductions across formats.",
    }


@router.get("/clusters")
def clusters():
    """Return 2D PCA projection and K-Means clusters over request features."""
    settings = get_settings()
    store_items = Store(settings.database_path).list_requests(50)
    result = analyze_clusters(store_items)
    return result


@router.post("/predict-length")
def predict_length(request: PredictLengthRequest):
    """Predict expected completion tokens using a Ridge regression model trained on fixture data."""
    return predict_output_length(
        input_tokens=request.input_tokens,
        language=request.language,
        format_constraint=request.format_constraint,
        max_tokens=request.max_tokens,
    )
