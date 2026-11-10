from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator

from .evidence import get_evidence
from .service import SAMPLES, get_service, source_url, validate_phrases

router = APIRouter(prefix="/api/v1/compression", tags=["compression"])


class CompressionRequest(BaseModel):
    text: str = Field(min_length=1, max_length=12000)
    method: Literal["heuristic", "crf"] = "heuristic"
    budget: float = Field(default=0.6, ge=0.1, le=1.0)
    protected_phrases: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("text")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter nonblank text.")
        return value


    @model_validator(mode="after")
    def valid_phrases(self) -> CompressionRequest:
        self.protected_phrases = validate_phrases(self.text, self.protected_phrases)
        return self


@router.post("/analyze")
def analyze(request: CompressionRequest):
    return get_service().analyze(request.text, request.method, request.budget, request.protected_phrases)


@router.get("/samples")
def samples():
    return {"kind": "upstream_regression_examples", "samples": [
        {**sample, "source_url": source_url(sample["source"])} for sample in SAMPLES
    ]}


@router.get("/compare")
def compare(budget: float = 0.6):
    if not 0.1 <= budget <= 1:
        raise HTTPException(422, "Budget must be between 0.1 and 1.")
    return {"kind": "local_execution_on_regression_examples", "rows": [
        {"sample_id": sample["id"], "label": sample["label"], "sample_source_url": source_url(sample["source"]),
         **get_service().analyze(sample["text"], method, budget)}
        for sample in SAMPLES for method in ("heuristic", "crf")
    ]}


@router.get("/evidence")
def evidence():
    try:
        return get_evidence()
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(503, "Historical evidence missing or fingerprint mismatch. "
                            "Run python scripts/import_compression_evidence.py.") from exc
