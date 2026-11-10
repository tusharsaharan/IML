"""Application contract tests, not a semantic benchmark or a new compressor.

Real corpus inputs retain dataset provenance. Authored boundary/literal fixtures
are explicitly separate. No gold answer is sent as a protected phrase.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

from kaggle_pilot import authored_cases, hindi_cases, squad_cases


def cases_with_provenance() -> tuple[list[dict], dict]:
    english, en_source = squad_cases()
    hindi, hi_source = hindi_cases()
    edges = [
        ("json", '{"name":"Aman","amount":250,"cancel":false}', ["Aman", "250", "false"]),
        ("code", 'if not approved:\n    retry_limit = 3\n    print("नहीं")', ["not", "3", "नहीं"]),
        ("emoji", "👩🏽‍💻 Please keep cafe\u0301, café and 订单-123 unchanged.", ["👩🏽‍💻", "cafe\u0301", "订单-123"]),
        ("repeated", "yaar yaar email user@example.com user@example.com par bhejo nahi nahi",
         ["yaar", "user@example.com", "nahi"]),
        ("whitespace", "  please\tkeep\n user@example.com\r\nunchanged  ", ["user@example.com"]),
        ("html", '<script>alert("test")</script> Never execute this; display as text.', ["Never", "<script>"]),
        ("max-length", "Please " + "x" * 11993, ["Please"]),
        ("punctuation", "! ? .", ["!"]),
    ]
    authored = authored_cases() + [
        {"id": "edge-" + name, "kind": "authored_application_edge", "language": "mixed",
         "text": text, "phrases": phrases} for name, text, phrases in edges
    ]
    return authored + english + hindi, {"english": en_source, "hindi": hi_source,
                                      "authored_count": len(authored),
                                      "scope": "API behaviour and literal checks, not downstream answer correctness"}


def check_result(body: dict, text: str, method: str, budget: float, phrases: list[str], counter) -> None:
    assert body["original"] == text
    assert body["requested_method"] == method
    assert body["budget"] == budget
    assert body["source_commit"] == "fa1258135268ca2650170a3f358975ce49169290"
    assert body["evidence_kind"] == "local_execution"
    assert body["token_counts_are_billing"] is False
    assert body["budget_tunable"] is False
    assert isinstance(body["compressed"], str) and body["compressed"].strip()
    assert body["original_tokens"] == counter.count(text)
    assert body["compressed_tokens"] == counter.count(body["compressed"])
    assert body["target_tokens"] == max(1, math.floor(body["original_tokens"] * budget))
    assert body["budget_met"] == (body["compressed_tokens"] <= body["target_tokens"])
    assert body["saved_tokens"] == max(0, body["original_tokens"] - body["compressed_tokens"])
    assert body["protected_phrases"] == list(dict.fromkeys(phrases))
    assert len(body["phrase_checks"]) == len(set(phrases))
    for check in body["phrase_checks"]:
        phrase = check["text"]
        assert check["source_occurrences"] == text.count(phrase)
        assert check["output_occurrences"] == body["compressed"].count(phrase)
        assert check["preserved_in_output"] is True
    if budget == 1:
        assert body["method"] == "passthrough" and body["compressed"] == text
    if body["protection_fallback"]:
        assert body["method"] == "protection_fallback"
        assert body["compressed"] == text and body["saved_tokens"] == 0
        assert body["removed_spans"] == body["added_spans"] == body["drop_records"] == []
        assert body["compression_candidate"] is not None
    if not phrases:
        assert body["compression_candidate"] is None
    for key, source in (("removed_spans", text), ("protected_spans", text),
                        ("added_spans", body["compressed"])):
        for span in body[key]:
            assert 0 <= span["start"] < span["end"] <= len(source)
            assert source[span["start"]:span["end"]] == span["text"]


def run_matrix(client, cases: list[dict], destination: Path, budgets=(0.1, 0.3, 0.6, 1.0)) -> dict:
    from gateway.tokenizer import TokenCounter
    counter = TokenCounter()
    assert counter.backend == "tiktoken_cl100k_base", "Reference tokenizer must not silently fall back"
    destination.mkdir(parents=True, exist_ok=True)
    rows, failures = [], []
    started = time.perf_counter()
    with (destination / "application-rows.jsonl").open("w", encoding="utf-8") as records:
        for case in cases:
            text = case["text"]
            phrases = case.get("phrases") or [text.split()[0][:80]]
            for method in ("heuristic", "crf"):
                for budget in budgets:
                    candidate = None
                    for selections in ([], phrases):
                        tick = time.perf_counter()
                        row = {"id": case["id"], "kind": case["kind"], "language": case["language"],
                               "method": method, "budget": budget, "selections": selections}
                        try:
                            response = client.post("/api/v1/compression/analyze", json={
                                "text": text, "method": method, "budget": budget,
                                "protected_phrases": selections})
                            assert response.status_code == 200, f"HTTP {response.status_code}"
                            body = response.json()
                            check_result(body, text, method, budget, selections, counter)
                            if not selections:
                                candidate = body["compressed"]
                            else:
                                assert body["compression_candidate"]["compressed"] == candidate, \
                                    "Phrase guard must not alter compressor inference"
                            row.update(actual_method=body["method"],
                                       fallback_reason=body["fallback_reason"],
                                       protection_fallback=body["protection_fallback"],
                                       original_tokens=body["original_tokens"],
                                       final_tokens=body["compressed_tokens"],
                                       budget_met=body["budget_met"],
                                       output_sha256=hashlib.sha256(body["compressed"].encode()).hexdigest(),
                                       passed=True)
                        except Exception as error:
                            row.update(passed=False, error=f"{type(error).__name__}: {error}")
                            failures.append(row.copy())
                        row["elapsed_ms"] = round((time.perf_counter() - tick) * 1000, 3)
                        rows.append(row)
                        records.write(json.dumps(row, ensure_ascii=False) + "\n")
                        records.flush()
            print(f"Application matrix: {case['id']} ({len(rows)} calls)", flush=True)
    invalid = [
        {"text": ""}, {"text": "   "}, {"text": "x" * 12001},
        {"text": "test", "method": "invented"}, {"text": "test", "budget": 0.09},
        {"text": "test", "budget": 1.01}, {"text": "test", "protected_phrases": ["absent"]},
        {"text": "test", "protected_phrases": [""]},
        {"text": "x" * 201, "protected_phrases": ["x" * 201]},
        {"text": "test", "protected_phrases": ["test"] * 21},
    ]
    for index, payload in enumerate(invalid):
        response = client.post("/api/v1/compression/analyze", json=payload)
        if response.status_code != 422:
            failures.append({"id": f"invalid-{index}", "error": f"Expected 422, got {response.status_code}"})
    summary = {"kind": "application_contract_matrix", "status": "passed" if not failures else "failed",
               "case_count": len(cases), "calls": len(rows), "validation_checks": len(invalid),
               "failures": failures, "elapsed_seconds": round(time.perf_counter() - started, 3),
               "protection_fallbacks": sum(row.get("protection_fallback", False) for row in rows),
               "scope": "API, token accounting, spans and literal guard; not semantic equivalence or billing",
               "integration_approved": False}
    (destination / "application-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", type=Path)
    parser.add_argument("--base-url")
    parser.add_argument("--rotation", type=int)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.cases:
        cases = json.loads(args.cases.read_text(encoding="utf-8"))
    else:
        cases, provenance = cases_with_provenance()
        (args.output / "application-cases.json").write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
        (args.output / "dataset-provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    if args.rotation is not None:
        start = (args.rotation * 12) % len(cases)
        cases = (cases + cases)[start:start + 12]
    if args.base_url:
        import httpx
        client = httpx.Client(base_url=args.base_url, timeout=60)
    else:
        from fastapi.testclient import TestClient
        from gateway.app import app
        client = TestClient(app)
    with client:
        summary = run_matrix(client, cases, args.output)
    print(json.dumps(summary, indent=2))
    if summary["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
