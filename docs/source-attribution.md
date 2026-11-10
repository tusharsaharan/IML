# Source attribution

This repository reuses selected implementation from `https://github.com/tusharsaharan/Research`.

- Import manifest: `docs/source-manifest.json`
- Import script: `scripts/import_research.py`
- Reference training scripts: `backend/scripts/reference/`

Record any substantial modification to imported files here:

| Date | File | Change | Reason |
|---|---|---|---|
| _pending_ |  |  |  |

## Compression application adapter (2026-11-09)

- `backend/src/gateway/features/compression/` delegates to the imported `Compressor`,
  `LinguisticCompressor`, `CRFTagger`, safety spans and `TokenCounter`. No imported
  algorithm files or trained weights were modified. The feature's tagger subclass
  observes successful prediction only, so upstream swallowed failures are not
  presented as CRF model execution. The bundled pickle is checked against the
  existing source manifest before it can be loaded.
- The three presets are verbatim prompts from the pinned Research regression
  tests. Each API response includes its source link. New application regression
  tests reuse those cases and add explicitly labelled adapter/error-path checks;
  they are not a new evaluation dataset or proof of semantic fidelity.
- `backend/data/compression_evidence/` contains byte-for-byte copies of `RESULTS.md`,
  `verified_review.json` and `stress_report.json` from Research commit
  `fa1258135268ca2650170a3f358975ce49169290`, under
  `backend/data/bench/hinglish_scaleup_full_20261029/`. Import with
  `python scripts/import_compression_evidence.py`. URLs, sizes and SHA-256 hashes
  are recorded in `backend/data/compression_evidence/provenance.json` and checked
  before serving. The feature only projects existing results for display.
- Historical raw answer/stress runs were **not rerun locally**. The source's
  exposed-development-data, single-model-family, strict-prefix-clipping and
  semantic-preservation limitations remain visible in the full report. Evaluation
  counts must not be described as concurrent users, deployment throughput,
   provider billing, losslessness, or an end-to-end speedup.

## Studio post-run phrase check (2026-11-09)

- Optional phrase checks live only in Tushar's compression feature adapter/UI.
  They inspect the existing compressor output after unmodified execution and
  retain the original on selected-literal occurrence loss. They do not implement
  a new research compressor, masking scheme, model or token-selection algorithm.
- The product idea follows structured/forced-retention controls documented by
  [Microsoft LLMLingua](https://github.com/microsoft/LLMLingua/blob/01b9e9481d7395e1e83a48df4a062b11f6304325/DOCUMENT.md).
  No LLMLingua code, dependency, weights or benchmark results were imported for
  this application guard. Compression still uses the pinned Research stack above.
- Imported algorithm files, weights, tokenizer and lexicons remain unchanged.
  Fingerprint tests check them against the existing source manifest. The final
  original-text fallback is not labelled as CRF compression or token savings;
  the actual candidate and any model fallback remain independently inspectable.
- New tests and the browser check are local application verification, **not a
  Kaggle evaluation or semantic-validation study**. The user requires prior
  Kaggle research validation before changes to the compressor itself.

## Kaggle application checks and source transfer (2026-11-10)

- `scripts/compression_research/application_matrix.py` tests the existing Studio
  API and post-run guard. SQuAD and pinned XQuAD Hindi inputs keep their recorded
  URLs/hashes and CC BY-SA 4.0 provenance. English/Hinglish/Hindi/mixed-script
  literal fixtures and boundary cases are authored QA data, not measured semantic
  equivalence or human-validated compressor labels.
- The private application batch used an allowlisted, file-hashed snapshot of the
  current adapter and imported dependencies. Existing application package
  `gateway/__init__.py` has its scaffold docstring and is snapshot-hashed separately;
  it is not asserted to match the upstream package initializer.
- The separate candidate-pilot transfer helper handles GitHub LF versus Windows
  CRLF source copies **only when converted bytes match the existing manifest's
  SHA-256**. It records the raw and manifest-matching hashes. Actual code changes
  still fail; binary weights are never newline-normalized. No imported source,
  inference logic, training data, manifest hash or bundled weight was changed.
- Candidate code/models remain confined to disposable private Kaggle CPU runs.
  They are not served by the application, and initial pilot results cannot
  authorize integration or a universal quality claim.

## Separate router reference import (2026-11-10)

- Repository: `https://github.com/tusharsaharan/code-mixed-gateway`, pinned commit
  `224d609237fcc67b5b83e029a9406e9fb7f51329`.
- 50 selected files are stored under
  `backend/scripts/reference/code_mixed_gateway_router/`, preserving upstream
  layout and exact Git-blob bytes. No imported algorithm source was modified.
- Separate manifest: `docs/router-source-manifest.json`; reproducible importer:
  `scripts/import_router.py`; scope and exclusions: `docs/router-import.md`.
  The existing Research source manifest and runtime modules are not overwritten.
- Included calibration CSVs are upstream archived threshold sweeps, not results
  rerun on IML, trained IML policies or evidence of live provider correctness.
- Missing weights/calibration, differing runbook proxy models, word-count versus
  tokenizer semantics, missing-embedding padding and reference-only training
  scripts are disclosed. No provider calls, training or model downloads occurred.
- Upstream repository metadata and tracked tree have no declared licence/licence
  file. Original attribution is retained; no MIT/Apache or other licence is inferred.
