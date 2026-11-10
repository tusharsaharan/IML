# Imported router source

**50 files** from [tusharsaharan/code-mixed-gateway](https://github.com/tusharsaharan/code-mixed-gateway)
are preserved at commit `224d609237fcc67b5b83e029a9406e9fb7f51329`.
This is a source import, **not a replacement of IML's running routing API**.

## Location and contents

Base folder: `backend/scripts/reference/code_mixed_gateway_router/`.
The upstream directory layout is retained under this folder so relative source/data
paths are understandable and offline tests can use a separate Python process.

| Within the base folder | Purpose |
|---|---|
| `backend/src/gateway/modules/m4_router/` | Cascade dispatch, difficulty features, learned-scorer wrapper |
| `backend/src/gateway/modules/m3_conformal/` | Threshold calibration, CRC, isotonic helper and calibration storage |
| `backend/src/gateway/` selected supporting files | Schemas, tokenizer, mock/HTTP clients, pricing and feature helpers |
| `backend/scripts/router_track/` | Audit, query preparation, labelling, grading, supervised/bandit training, calibration and evaluation source |
| `backend/scripts/freeze_splits.py` | Upstream split-freezing checks |
| `backend/experiments/cascade_routing/scripts/` | Separate heuristic/calibration and Laya scoring/routing reference scripts |
| `backend/experiments/cascade_routing/data/calibration_*.csv` | Two archived upstream threshold sweeps; not application-certified thresholds |
| `backend/tests/test_m3.py`, `test_m4.py` | Original offline calibration/router tests |
| READMEs and `backend/pyproject.toml` | Original runbook and dependency context; do not install this partial package as the application |

## Reproduce or verify

`docs/router-source-manifest.json` records the source commit, every path, exact Git-blob
SHA-256, byte sizes, missing artifacts and exclusions. The existing Research manifest
`docs/source-manifest.json` is unchanged.

An IML-authored local `.gitattributes` preserves the imported bytes across Git
checkouts; it is listed separately from the 50 upstream files.

From the IML root:

```powershell
# Re-import only into a clean destination; existing files are never overwritten.
.\.venv\Scripts\python.exe scripts/import_router.py --source "PATH_TO_PINNED_CHECKOUT"

# These work with the existing IML environment; no installs or model downloads.
.\.venv\Scripts\python.exe scripts/import_router.py --verify
.\.venv\Scripts\python.exe scripts/routing/check_import.py
```

The importer reads only committed blobs from the pinned repository, not dirty checkout
files. It preflights collisions, including its separate manifest, before writing.
The check runner verifies hashes and runs upstream plus authored contract checks in a
separate process. Network connections are blocked (apart from Windows' internal
event-loop socketpair construction). Only supplied mock/recording clients are exercised.

## What remains unavailable

- The tracked repository lacks `logreg.pkl`, `xgb.json`, `bandit_head.pt`, frozen
  `thresholds.json` and `calibration_real.jsonl` at the paths expected by `LearnedScorer`.
  None was fabricated or replaced with IML's differently sourced artifacts.
- `LearnedScorer` currently loads only logistic-regression pickles. With no weights,
  it reports heuristic fallback. With an embedding-trained classifier, its zero-filled
  missing embedding columns are **not** full trained-inference parity.
- The training scripts write to `backend/data/router_track/`, whereas the older runtime
  wrapper expects `backend/data/router_artifacts/` and other `backend/data/` files.
  This handoff needs an explicit adapter; files were not silently relocated.
- `run00_audit.py` imports upstream `gateway.service`, intentionally excluded with its
  unrelated compression/gateway dependency tree. It remains reference-only.
- Labelling/refill scripts make provider calls; supervised training can download
  MiniLM; bandit training requires PyTorch. They were **not executed** for this import.
  Several scripts run work at module import time: do not import them into IML's API.
- Laya scripts require a separate implementation/checkpoint, with original `D:/laya`
  and other machine-specific paths. No Laya package or checkpoint was downloaded.
- Raw prompt/answer datasets, databases, credentials, notebooks, PDFs/figures and scratch
  material are excluded. The two CSV sweeps alone do not reproduce the upstream study.
- No licence file or declared repository licence was found. Attribution is retained;
  no licence was inferred.

## Interpretation cautions

- Gateway `DifficultyScorer.token_count` means whitespace word count, not tokenizer
  tokens. The standalone experiment uses different features and a different threshold
  inequality/risk denominator; the two implementations are not interchangeable.
- `CascadeRouter(dry_run=True)` **still invokes its supplied client**. Use
  `MockLLMClient`, not a live HTTP client, for offline execution.
- The newer router-track runbook uses Groq `openai/gpt-oss-20b` / `openai/gpt-oss-120b`.
  The older notebook runbook describes Llama proxy models. Those are version-specific
  configurations, not measured GPT-4o results.
- Lexical-proxy grading, authored labels and model opinions must not be relabelled as
  measured downstream correctness. Reference pricing/counts are not provider billing.

IML's existing routing API/page, imported Research router and compressor are untouched.
API integration should be a separate routing-feature adapter change once the actual
artifacts, feature contract and provenance have been confirmed.

## Verification completed

- All 50 imported SHA-256 fingerprints matched.
- 18 isolated checks passed: seven upstream tests and 11 authored import/contract
  cases, including missing-artifact fallback and threshold-boundary behaviour.
- IML's backend suite passed 128 tests, including five import-safety regressions.
- `npm run check` passed typechecking, 16 frontend tests and the production build.
- Targeted Ruff and `git diff --check` passed. No upstream source was reformatted.
