"""Read and project existing evidence; do not author or recalculate results."""
from __future__ import annotations

import hashlib
import json

from .service import ROOT, source_url


def get_evidence() -> dict:
    directory = ROOT / "data/compression_evidence"
    manifest = json.loads((directory / "provenance.json").read_text(encoding="utf-8"))
    files = {}
    for row in manifest["files"]:
        content = (directory / row["file"]).read_bytes()
        if hashlib.sha256(content).hexdigest() != row["sha256"]:
            raise ValueError(f"Evidence fingerprint mismatch: {row['file']}")
        files[row["file"]] = json.loads(content) if row["file"].endswith(".json") else content.decode("utf-8")
    review = files["verified_review.json"]
    rows = []
    for model, metrics in review["metrics"].items():
        for target in (0.5, 0.33, 0.75, 0.25):
            candidate = f"bqwen35b_span@{target}"
            bm25 = f"bm25_strict@{target}"
            lingua = f"llml2L_strict@{target}"
            comparison = next(row for row in review["comparisons"] if row["model"] == model
                              and row["method"] == candidate and row["reference"] == bm25
                              and "selection_source_overlap" not in row)
            rows.append({"model": model, "target": target, "n": metrics[candidate]["n"],
                         "original_accuracy": metrics["original"]["accuracy"],
                         "candidate_accuracy": metrics[candidate]["accuracy"],
                         "bm25_accuracy": metrics[bm25]["accuracy"],
                         "llmlingua_accuracy": metrics[lingua]["accuracy"],
                         "delta_vs_bm25": comparison["delta"], "ci95": comparison["ci95"],
                         "context_kept": metrics[candidate]["mean_context_ratio"],
                         "full_prompt_kept": metrics[candidate]["mean_full_prompt_ratio"],
                         "invalid": metrics[candidate]["invalid"]})
    return {"kind": manifest["kind"], "provenance": manifest,
            "verification_scope": manifest["verification_scope"],
            "qa_records": review["qa_records"], "qa_items": review["qa_items"],
            "source_passages": review["source_passages"], "stress_texts": review["stress_texts"],
            "stress_records": review["stress_records"], "interpretation": review["interpretation"],
            "candidate": "Qwen3.6-35B question-only evidence ranking with original-span packing",
            "rows": rows, "results_markdown": files["RESULTS.md"],
            "results_url": source_url("backend/data/bench/hinglish_scaleup_full_20261029/RESULTS.md"),
            "release_url": "https://github.com/tusharsaharan/Research/releases/tag/evidence-2026-11-07",
            "stress": files["stress_report.json"],
            "limits": ["Historical exposed development data, not a fresh confirmatory test.",
                       "All four answer models belong to one family.",
                       "Paired passage-clustered intervals are exploratory and unadjusted for multiple comparisons.",
                       "The candidate uses a 35B ranker; it is not the local CPU heuristic or CRF demo.",
                       "Budget compliance and correct answers do not establish meaning preservation.",
                       "Ranker overhead exceeded observed generation savings; no end-to-end speedup claim.",
                       "Stress outputs include empty, punctuation-only and literal-deletion failures.",
                       "Reference-token caps are not provider billing or production throughput."]}
