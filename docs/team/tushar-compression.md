# Tushar — Compression Studio

## Goal
Build an interactive prompt-compression workspace that shows what the system keeps, removes and protects before a request is sent.

## Own
- Frontend: `src/features/compression/`
- Backend: `backend/src/gateway/features/compression/`
- Tests: `backend/tests/test_compression*.py`, feature-specific frontend tests if added.

## Build
1. Replace the starter API with the imported compressor stack (`gateway.modules.m2_compressor`) and `TokenCounter`.
2. Add methods the UI can choose: `heuristic` and `crf` at minimum.
3. Return removed spans, protected spans, token counts, compression ratio and a short method note.
4. Add a budget/strength control and show how output changes.
5. Create a comparison table for at least two methods on three sample prompts.
6. Show a "send compressed text to studio" action using the shared chat contract when available.

## Demo cases
- Verbose Hinglish support request with names or numbers (protected content should remain).
- English request with filler/greeting text.
- Hindi or mixed-script request showing token reduction.

## ML/course angle
- Sequence labeling / feature-based compression (CRF) and heuristic baseline.
- Explain precision of protected spans and the trade-off between brevity and information retention.

## Done when
- `/api/v1/compression/analyze` returns real method output.
- The page renders original/compressed text, highlights and token metrics.
- Targeted backend tests pass for span protection and non-empty output.

## Application status (2026-11-09)

Implemented within Tushar's feature directories:

- `/compression` now has a prompt editor, actual heuristic/CRF selection,
  source/output highlights, protected-literal checks, algorithm drop records,
  reference-token metrics, honest fallbacks and JSON exports.
- `/api/v1/compression/analyze` uses the imported Research stack and bundled CRF
  checkpoint. The checkpoint fingerprint must match the existing import manifest.
  No new models, paid services, GPU jobs or model downloads were introduced.
- `/api/v1/compression/samples` exposes three source-linked upstream regression
  examples. `/api/v1/compression/compare` runs both methods on those examples.
  Unchanged output and model fallback are retained, including the Hindi case.
- `/api/v1/compression/evidence` exposes fingerprinted historical development
  results: 75,600 answer records, 900 questions, 488 source passages, and 80,000
  stress outputs over 10,000 texts. These counts describe the historical study,
  not this application's traffic capacity. The 35B evidence ranker is not served
  by the local CPU demo. Accuracy losses versus original prompts, invalid outputs,
  confidence-interval caveats and stress failures remain visible.

### Deliberate boundaries

The imported heuristic/CRF implementations have no rate-tuning parameter. The
budget control therefore checks the target versus actual reference-token counts;
it does **not** invent a strength algorithm or truncate to manufacture compliance.
At 100%, the original prompt is retained. Genuine rate-tuned compression remains
an optional future integration requiring a separately approved local model.

The shared Studio/chat pipeline is not wired yet. Export Studio request downloads
the documented chat contract with compression disabled (already compressed text).
It does not send a live call, generate an answer, or change shared interfaces.

Regex protection does not automatically detect arbitrary names, all numbers, or
all Hindi negations. Literal preservation is not semantic equivalence. The CRF
checkpoint's deterministic/synthetic-teacher training must not be relabelled as
human-validated semantic correctness.

### Run and verify

```powershell
# From repository root:
npm run dev
# Open http://127.0.0.1:8080/compression
npm run check

# From backend/:
..\.venv\Scripts\python.exe -m pytest tests/test_compression.py tests/test_compression_evidence.py tests/test_health.py -q
```

Verification: 61 targeted backend/health tests passed; 8 frontend tests passed;
TypeScript checking, production build and targeted Ruff checks passed. These are
application checks, not a rerun of the historical answer-model study.

For the optional real-browser smoke check with an already installed Playwright CLI:

```powershell
playwright-cli -s=iml-compression open http://127.0.0.1:8080/compression --browser=chrome
playwright-cli -s=iml-compression run-code --filename=scripts/check_compression_browser.js
playwright-cli -s=iml-compression close
```

The real-browser smoke check passed: actual CRF output (14 to 10 reference
tokens), literal highlighting, six comparisons, four historical model rows,
unchanged 100% output, stale-result controls, contract download and an explicitly
injected QA-only service failure. The 390px mobile viewport had no whole-page
overflow, and no JavaScript page errors were recorded.
Screenshots are saved in the ignored `test-results/compression/` directory.
