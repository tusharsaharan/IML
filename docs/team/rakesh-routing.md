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