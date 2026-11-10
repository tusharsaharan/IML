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
..\.venv\Scripts\python.exe -m pytest tests/test_compression.py tests/test_compression_phrases.py tests/test_compression_evidence.py tests/test_health.py -q
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

## Next increment: optional Studio phrase check (2026-11-09)

- **Always keep these phrases** accepts up to 20 exact, case-sensitive phrases,
  each up to 200 Unicode code points. The editor uses one phrase per line, ignores
  blank lines and deduplicates repeated selections. Literal spaces are preserved.
  A phrase absent from the source is rejected; it is not inserted into the prompt.
- The adapter runs the existing compressor on the **unchanged original input**,
  then checks non-overlapping literal occurrence counts. Losing any selected
  occurrence triggers an explicitly labelled `protection_fallback` retaining the
  whole original. There is no masking, altered token selection, re-inference,
  new model, retraining, truncation, or imported-code change.
- Final-output metrics report zero savings on protection fallback. The actual
  compressor candidate, method, diffs, token counts, drop records and model
  fallback reason remain separate in the audit. Selected literals have Unicode
  offsets and both candidate/final survival checks. These checks do not establish
  semantic equivalence, position preservation or answer correctness.
- Editing selections makes previous output stale and disables copy/download/
  Studio export. Invalid selections block analysis. An older running backend
  that ignores the new request field is rejected for protected requests.
- Audit download includes both final output and the candidate. Studio export
  includes **only the final output**, with compression disabled as before. The
  six-preset comparison deliberately runs without custom selections. Other
  teammates' features and the shared chat contract are unchanged.

### Feature-local API addition

`POST /api/v1/compression/analyze` accepts an optional `protected_phrases` list:

```json
{"text":"yaar matlab mera email user@example.com par bhejo na","method":"crf","budget":0.6,"protected_phrases":["yaar","user@example.com"]}
```

New response fields: `protected_phrases`, `phrase_checks`, `protection_fallback`,
and `compression_candidate` (null when checks are disabled). `method` describes
the final application output; on protection fallback the candidate's `method`
still describes the actual imported execution. This addition is **Studio-only**,
not a change to the shared chat/compression pipeline.

### Research boundary and verification

The user requires **prior Kaggle validation before any research compressor
change**. No Kaggle evaluation was performed for this increment, and no research
change is claimed. Local tests validate the application guard only.

- 91 targeted backend/health tests passed, including literal multiplicity,
  Unicode, bounds, validation, unchanged inputs and explicit fallback checks.
- `npm run check` passed: 16 frontend tests, TypeScript checking and production
  build. Targeted Ruff checks passed.
- SHA-256 checks passed for the imported compressor dependencies and weights
  against the existing Research import manifest.
- A read-only comparison against the previous committed adapter matched all
  existing output/audit fields on 56 runs (seven prompts, two methods, four
  targets), excluding elapsed time and the new optional response fields.
- The real-browser check passed on the built frontend (temporary preview port
  8081) and a temporary local backend on port 8001, forwarding real compression
  requests without replacing
  successful data. It checked candidate retention, unchanged surviving-literal
  output, phrase-edit export blocking, invalid phrases, three Hindi selections,
  actual downloaded JSON, 100% passthrough and the existing QA-only service error.
  Both normal and fallback 390px views had no whole-page overflow; there were
  zero JavaScript page errors. Screenshots/downloads remain under ignored
  `test-results/compression/`.
- A separate browser check against the still-running older backend confirmed
  that protected requests are rejected with a restart instruction, without
  accepting its unchecked output or causing a JavaScript page error.
- For stable download checks, use a built preview rather than hot reload: the
  CLI's generated JSON files can cause the development server to reload the
  page during a test. These reloads are not compressor failures.
- The regular `npm run dev` backend does not auto-reload Python. Restart it after
  pulling these changes to use the new feature on the standard port 8000.

### Explicit Hinglish and English verification (2026-11-09)

- Added API regression coverage for both languages and both methods across the
  two upstream presets plus four labelled local QA cases (negations and repeated
  phrases). Empty selections preserve default execution; surviving selections
  preserve the candidate; lost selections retain the original. Repeated losses,
  case-sensitive validation and 100% passthrough are checked per case.
- All 103 backend/health tests and targeted Ruff checks passed. These are local
  application tests, not a new research dataset or semantic evaluation.
- Chrome on the standard dev setup (8080 frontend, 8000 backend) passed 36 real
  UI/API runs covering six prompts, two methods and three selection states.
  All 12 downloaded Studio requests retained the original on protection fallback
  and disabled double compression. Both language presets passed at 390px without
  whole-page overflow. Zero JavaScript page errors were recorded. Browser output
  was written under the approved temporary directory to avoid dev hot reloads.
- Observed default reference tokens, heuristic / CRF request respectively:
  Hinglish preset 14→10 / 14→10; English filler 10→9 / 10→9 (heuristic fallback);
  Hinglish negation QA 22→18 / 22→15; English negation QA 13→13 / 13→9;
  repeated Hinglish QA 9→5 / 9→4; repeated English QA 14→12 / 14→12
   (heuristic fallback). Unchanged output and CRF fallback are not hidden. Selected
   negation survival is a literal observation, not proof of preserved meaning.

## Kaggle application validation and bounded timers (2026-11-10)

- The new private CPU batch
  `tusharsaharan18/iml-compression-application-20261110`, version 1, completed
  successfully on four CPU cores. It tested a hash-recorded, allowlisted snapshot
  of the actual application, without `.env`, credentials, runtime data or GPU use.
- The batch passed 103 existing backend/health tests and 1,536 actual API calls
  across 96 inputs: 32 SQuAD English multi-passage items, 32 XQuAD Hindi passages,
  24 explicitly authored English/Hinglish/Hindi/mixed-script literal cases and
  eight authored JSON/code/Unicode/whitespace/repetition/HTML/length/punctuation
  cases. Ten invalid-request checks passed. Corpus URLs, revisions, selection
  seed and downloaded-byte hashes are saved with the artifacts. Gold answers
  are not supplied as protected phrases.
- All 1,536 local/Kaggle rows agreed on output hashes, final token counts, actual
  method and protection fallback. This verifies application parity, not semantic
  equivalence, provider billing or unseen downstream-answer correctness.
- The new reusable checks are in `scripts/compression_research/application_matrix.py`.
  That directory name preserves the existing evaluation-script location; the
  application matrix is a contract test, not a replacement research algorithm.
- A separate LLMLingua-2 candidate pilot remains isolated from the application.
  Its first run stopped before producing results: the Windows import manifest
  hashes CRLF source copies while GitHub raw serves LF. Transfer verification
  now accepts only a newline conversion whose bytes match the existing hash;
  content changes and binary-weight normalization still fail. The failed notebook
  and artifacts are preserved, and a fresh `...candidate-pilot-20261110b` run was
  submitted. The repaired run was observed **RUNNING**, with logs recording
  completed English, Hinglish and Hindi compression rows. Final QA scores and
  candidate acceptance are still pending. No new Studio method has been enabled.
- Windows Task Scheduler registered **20 one-shot checks, 30 minutes apart**,
  from 10:20:35 to 19:50:35 IST on 2026-11-10. Task name:
  `IML-Compression-20261110-095432`. Each slot checks pinned Kaggle job states,
  downloads bounded completed artifacts, reruns the backend suite and `npm run check`,
  exercises 12 rotating corpus/fixture inputs against the live local API, and
  runs the existing browser smoke check in its own temporary Chrome session.
- The timer smoke run passed all four application checks, including 192 live API
  calls and ten invalid requests. The normal browser check also passed selected
  phrase guards, candidate retention, actual exports, Unicode highlights, six
  comparisons, 100% passthrough and 390px layouts. The sole error-level console
  entry was the explicitly injected QA-only HTTP 503, not an unexpected failure.
- Latest local backend verification passed **123 tests** and also covers transfer verification, private
  snapshot exclusions, fabricated token-count rejection, timer interval/precision
  handling, pinned API version labels and exclusion of Kaggle credentials from
  frontend/browser subprocess environments. `npm run check` and targeted Ruff
  checks passed again.
- Timer state, logs, corpus inputs and Kaggle artifacts are outside the project:
  `C:\Users\tusha\AppData\Local\Temp\opencode\iml-overnight-20261110\`.
  Credentials are Windows-user-encrypted separately, never included in notebook
  source or passed to frontend builds/browser tests. The exposed chat token must
  be revoked/rotated; doing so before monitoring ends requires a replacement.
- Timers require the computer to remain **on, awake, plugged in and signed in**
  with internet access. No wake/power settings were changed. Kaggle batch work
  does not require artificial browser activity. Timers run fixed checks and save
  failures; they do not provide unattended AI reasoning, edit source code, restart
  failed jobs indefinitely, enable candidates, commit or push.

To stop this particular timer task:

```powershell
Unregister-ScheduledTask -TaskName 'IML-Compression-20261110-095432' -Confirm:$false
```
