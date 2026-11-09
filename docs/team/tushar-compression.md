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