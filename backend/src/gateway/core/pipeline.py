"""One server-owned request lifecycle; feature adapters never call each other."""
from __future__ import annotations

import hashlib
import json
import re
from time import perf_counter
from typing import Literal

import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from starlette.concurrency import run_in_threadpool

from gateway.features.cache import service as cache
from gateway.features.compression.service import get_service as compression_service, validate_phrases
from gateway.features.insights.models import predict_output_length
from gateway.features.routing.features import extract_features
from gateway.features.routing.service import get_service as routing_service
from gateway.tokenizer import TokenCounter

from .config import get_settings
from .providers import Provider
from .store import Store

router = APIRouter(prefix="/api/v1", tags=["pipeline"])


class Options(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CompressionOptions(Options):
    enabled: bool = True
    method: Literal["heuristic", "crf"] = "heuristic"
    budget: float = Field(default=0.6, ge=0.1, le=1)
    protected_phrases: list[str] = Field(default_factory=list, max_length=20)


class RoutingOptions(Options):
    enabled: bool = True
    policy: Literal["economy", "balanced", "quality"] = "balanced"


class CacheOptions(Options):
    enabled: bool = True
    # Approximate similarity is a candidate, never automatic proof of equivalence.
    accept_semantic: bool = False


class OutputOptions(Options):
    format_constraint: Literal["3 bullets", "JSON only", "no preamble"] | None = None
    max_tokens: int = Field(default=120, ge=1, le=4096)


class ChatRequest(Options):
    text: str = Field(min_length=1, max_length=4000)
    language: Literal["auto", "en", "hinglish", "hi"] = "auto"
    mode: Literal["demo", "live"] = "demo"
    compression: CompressionOptions = Field(default_factory=CompressionOptions)
    routing: RoutingOptions = Field(default_factory=RoutingOptions)
    cache: CacheOptions = Field(default_factory=CacheOptions)
    output: OutputOptions = Field(default_factory=OutputOptions)
    compare: Literal[False] = False

    @field_validator("text")
    @classmethod
    def nonblank(cls, value):
        if not value.strip() or not any(char.isalnum() for char in value):
            raise ValueError("Enter a question containing letters or numbers.")
        return value

    @model_validator(mode="after")
    def phrases(self):
        self.compression.protected_phrases = validate_phrases(self.text, self.compression.protected_phrases)
        return self


def _scope(request: ChatRequest, base: str, settings) -> str:
    # Policy, models, transformations and answer instructions must not share keys.
    # Increment version when the demo knowledge/prompt template changes.
    if not re.fullmatch(r"[A-Za-z0-9:_-]{1,128}", base):
        raise HTTPException(422, "Invalid X-Cache-Scope.")
    context = {
        "version": "pipeline-v1", "scope": base, "mode": request.mode,
        "language": request.language, "routing": request.routing.model_dump(),
        "compression": request.compression.model_dump(), "output": request.output.model_dump(),
        "endpoint": settings.api_base_url, "models": [settings.cheap_model, settings.strong_model],
    }
    digest = hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()[:32]
    return f"pipeline:{digest}"


def _demo_output(text: str, output: OutputOptions, counter: TokenCounter) -> tuple[str, bool]:
    """Format authored text locally, then limit reference tokens; no model claim."""
    if output.format_constraint == "3 bullets":
        text = "\n".join(f"- {part}" for part in re.split(r"(?<=[.!?])\s+", text)[:3])
    render = (lambda value: json.dumps({"answer": value}, ensure_ascii=False)) if output.format_constraint == "JSON only" else (lambda value: value)
    answer = render(text)
    truncated = counter.count(answer) > output.max_tokens
    # A character-prefix search keeps Unicode intact. Verify the final bound even
    # for non-monotone subword segmentations and preserve valid JSON.
    if truncated:
        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if counter.count(render(text[:mid])) <= output.max_tokens:
                lo = mid
            else:
                hi = mid - 1
        answer = render(text[:lo].rstrip())
        while text[:lo] and counter.count(answer) > output.max_tokens:
            lo -= 1
            answer = render(text[:lo].rstrip())
        if counter.count(answer) > output.max_tokens or not answer.strip():
            answer = "0" if output.format_constraint == "JSON only" else "…"
    return answer, truncated


async def execute(request: ChatRequest, base_scope: str) -> dict:
    started = perf_counter()
    settings = get_settings()
    provider = Provider(settings.model_copy(update={"mode": request.mode}))
    if request.mode == "live" and (settings.mode != "live" or not provider.is_live()):
        raise HTTPException(503, "Live mode requires IML_MODE=live, endpoint, API key and both model IDs. Restart the backend after configuration.")
    counter = TokenCounter()
    features = extract_features(request.text)
    language = request.language if request.language != "auto" else {
        "english": "en", "hindi": "hi", "mixed_script": "hinglish", "hinglish": "hinglish",
    }.get(features.language_group, "en")
    scope = _scope(request, base_scope, settings)
    trace = []

    def stage(name: str, status: str, note: str):
        trace.append({"stage": name, "status": status, "note": note})

    cached = cache.lookup(request.text, language, scope) if request.cache.enabled else {"hit": False, "match_type": "disabled"}
    # Private requests bypass reuse as well as learning.
    private = not cache.reusable(request.text, "")
    strict_same = re.sub(r"\s+", " ", request.text).strip().casefold() == re.sub(
        r"\s+", " ", cached.get("matched_question") or ""
    ).strip().casefold()
    accepted = bool(cached["hit"] and not private and (
        (cached["match_type"] == "exact" and strict_same)
        or (cached["match_type"] == "semantic" and request.cache.accept_semantic)
    ))
    cache_result = {**cached, "hit": accepted, "candidate_hit": cached["hit"], "scope": scope, "stored": False}
    if cached["hit"] and not accepted:
        cache_result["note"] = "Candidate not reused: private content, changed punctuation/operators, or approximate reuse was not enabled."
    stage("cache", "hit" if accepted else "miss" if request.cache.enabled else "skipped", cache_result.get("note", "Cache disabled."))
    comp = route = prediction = None
    model = None
    usage = {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None}
    provider_called = False
    prompt = request.text
    demo_truncated = False
    if accepted:
        answer = cached["answer"]
        source = "cache"
        origin = cached["source"]
        demo_truncated = request.mode == "demo" and origin.endswith(":truncated")
        stage("compression", "skipped", "Cached answer reused; no compression needed.")
        stage("routing", "skipped", "Cached answer reused; no model selected.")
        stage("generation", "skipped", "No provider call or new provider tokens.")
    else:
        if request.compression.enabled:
            comp = compression_service().analyze(request.text, request.compression.method, request.compression.budget, request.compression.protected_phrases)
            prompt = comp["compressed"]
            stage("compression", "completed", comp.get("fallback_reason") or f"Actual method: {comp['method']}.")
        else:
            stage("compression", "skipped", "Compression disabled; original text retained.")
        if request.routing.enabled:
            # Preserve original feature semantics even when heuristic fallback is active.
            route = routing_service().predict(request.text, request.routing.policy)
            route["compressed_token_count"] = counter.count(prompt)
            tier = route["selected_tier"]
            stage("routing", "completed", route["note"])
        else:
            tier = "cheap"
            stage("routing", "skipped", "Routing disabled; economy model selected explicitly.")
        model = settings.strong_model if tier == "strong" else settings.cheap_model
        prediction = predict_output_length(max(1, counter.count(prompt)), language, request.output.format_constraint, request.output.max_tokens)
        if request.mode == "demo":
            generation = provider.answer_fixture(request.text)
            answer, demo_truncated = _demo_output(generation.text, request.output, counter)
            source = "authored-demo" if generation.source != "fallback" else "demo-fallback"
            origin = generation.source
        else:
            try:
                generation = await provider.generate(prompt, model, max_tokens=request.output.max_tokens, format_constraint=request.output.format_constraint)
            except httpx.TimeoutException as exc:
                raise HTTPException(504, "The configured provider timed out. No answer was saved.") from exc
            except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
                raise HTTPException(502, "The configured provider failed or returned an invalid answer. No answer was saved.") from exc
            answer = generation.text
            provider_called = True
            source = origin = "live-provider"
            usage = {key: getattr(generation, key) for key in usage}
        stage("generation", "completed", "Authored fixture formatted locally; cap uses reference tokens." if request.mode == "demo" else "Selected model called with format instructions and max_tokens.")
        if request.cache.enabled and source != "demo-fallback" and cache.reusable(request.text, answer):
            saved_source = f"{source}:{origin}" + (":truncated" if demo_truncated else "")
            cache_result["cache_id"] = cache.remember(request.text, answer, language, saved_source, scope)
            cache_result["stored"] = cache_result["cache_id"] is not None
            cache_result["store_reason"] = "Saved for repeats in this configuration." if cache_result["stored"] else "Existing normalized key retained; the new answer was not saved."
        else:
            cache_result["store_reason"] = "Caching disabled, private content, or generic demo fallback."

    original_tokens = counter.count(request.text)
    prompt_tokens = counter.count(prompt)
    output_tokens = counter.count(answer)
    # Include the format instruction in reference input accounting, while keeping
    # provider-reported usage separate (chat-envelope overhead is unknown).
    sent_tokens = counter.count(f"Answer format: {request.output.format_constraint}.\n\n{prompt}") if request.output.format_constraint else prompt_tokens
    cost = None
    cost_basis = "unknown"
    if provider_called:
        tier = route["selected_tier"] if route else "cheap"
        prefix = "strong" if tier == "strong" else "cheap"
        input_price, output_price = getattr(settings, f"{prefix}_input_price"), getattr(settings, f"{prefix}_output_price")
        if input_price is not None and output_price is not None:
            pin = usage["prompt_tokens"] if usage["prompt_tokens"] is not None else sent_tokens
            pout = usage["completion_tokens"] if usage["completion_tokens"] is not None else output_tokens
            cost = (pin * input_price + pout * output_price) / 1_000_000
            cost_basis = "configured_prices_provider_usage" if usage["prompt_tokens"] is not None and usage["completion_tokens"] is not None else "configured_prices_reference_estimate"
    else:
        cost, cost_basis = 0.0, "no_provider_call"
    result = {
        "mode": request.mode, "language": language, "answer": answer,
        "answer_source": source, "origin_source": origin, "model": model,
        "provider_called": provider_called, "cache": cache_result,
        "compression": comp, "routing": route, "prediction": prediction,
        "output": {**request.output.model_dump(), "demo_truncated": demo_truncated,
                   "note": "Demo limits are local reference-token limits; live limits are sent to the provider. Format compliance is not guaranteed."},
        "usage": {"reference_original_tokens": original_tokens, "reference_prompt_tokens": prompt_tokens,
                  "reference_sent_tokens": 0 if accepted else sent_tokens,
                  "reference_output_tokens": output_tokens, "tokenizer_backend": counter.backend,
                  "input_tokens_saved": max(0, original_tokens - prompt_tokens), "provider": usage},
        "cost": {"usd": cost, "basis": cost_basis, "note": "Configured price calculation, not a provider invoice. No counterfactual savings are measured."},
        "trace": trace,
    }
    stage("insights", "completed", "Reference counts, provenance and provider usage recorded in SQLite.")
    result["elapsed_ms"] = round((perf_counter() - started) * 1000, 2)
    record = {
        **result, "input_tokens": 0 if accepted else sent_tokens, "output_tokens": output_tokens,
        "route": route["selected_tier"] if route else "cache" if accepted else "cheap",
        "cache_hit": accepted, "compressed": comp is not None and prompt != request.text,
        "cost_usd": cost, "max_tokens": request.output.max_tokens,
        "format_constraint": request.output.format_constraint,
    }
    result["request_id"] = Store(settings.database_path).record_request(request.text, language, record)
    return result


@router.post("/chat")
async def chat(request: ChatRequest, cache_scope: str = Header(default="public", alias="X-Cache-Scope")):
    # CPU feature calls and SQLite run off the event loop. Async provider I/O stays
    # inside that worker's lifecycle, so concurrent requests keep health responsive.
    import asyncio
    return await run_in_threadpool(lambda: asyncio.run(execute(request, cache_scope)))
