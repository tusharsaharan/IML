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
