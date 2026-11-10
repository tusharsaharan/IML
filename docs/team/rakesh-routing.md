# Rakesh — Smart Router

## Goal
Build a model-selection workspace that explains why a request is routed to an economy or stronger model.

## Own
- Frontend: `src/features/routing/`
- Backend: `backend/src/gateway/features/routing/`
- Scripts/artifacts: `backend/scripts/`, `backend/data/artifacts/` routing outputs.

## Build
1. Extract request features using imported utilities: token/character length, language group, code-mix ratio and any available difficulty signals.
2. Train and compare at least logistic regression, random forest and a small MLP on the prepared routing dataset/fixtures.
3. Save a compact metrics artifact (accuracy, precision/recall or F1, confusion matrix, selected threshold/policy notes).
4. Expose `economy`, `balanced` and `quality` policies through the API.
5. Show the selected model, score, threshold, feature values and model comparison in the UI.
6. Add a short explanation panel: which features pushed the decision toward the stronger model.

## Demo cases
- Short English request routed economically.
- Long Hinglish or mixed-script request routed upward.
- Same request under different policies to show controlled trade-offs.

## ML/course angle
- Classification, ensembles and a neural network baseline.
- Feature engineering, evaluation metrics and decision thresholds.

## Done when
- `/api/v1/routing/predict` returns policy-aware routing with real features.
- The page shows model comparison metrics from a saved artifact or fixture.
- Targeted tests cover feature extraction and policy threshold behavior.

## Router source imported (2026-11-10)

- Imported 50 pinned router/dependency/training/test/reference files from
  `tusharsaharan/code-mixed-gateway@224d609237fcc67b5b83e029a9406e9fb7f51329`.
- Location: `backend/scripts/reference/code_mixed_gateway_router/`; directory
  structure and original source bytes are preserved. Existing Research modules,
  `/api/v1/routing/predict` and the routing page were not replaced.
- Import manifest: `docs/router-source-manifest.json`. Importer:
  `scripts/import_router.py` (collision-refusing, commit-pinned, verify mode).
- See `docs/router-import.md` for dependencies, source limitations and offline
  test commands. `scripts/routing/check_import.py` isolates the upstream gateway
  namespace and blocks network connections during verification.
- The upstream tracked tree does not contain the trained learned-scorer weights
  or frozen operational calibration artifacts. No model was trained/downloaded
  and no provider was called as part of the import. The learned wrapper falls
  back to heuristic without its artifacts; the two imported sweep CSVs are
  historical reference data, not calibrated IML application policies.
- A feature adapter and verified artifacts are still required for application
  integration. Do not mix the older wrapper's paths/features with the newer
  training track or the separate Laya experiment without an explicit handoff.
- Verification: 50 source hashes matched; 18 isolated router checks and 128 IML
  backend tests passed; `npm run check` passed 16 frontend tests, typechecking and
  the build. Import/verification/test helpers passed targeted Ruff checks.
