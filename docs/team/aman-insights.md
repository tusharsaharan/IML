# Aman — Token & Cost Insights

## Goal
Build the analytics workspace that helps users compare token usage, costs and request patterns across languages and optimisation choices.

## Own
- Frontend: `src/features/insights/`
- Backend: `backend/src/gateway/features/insights/`
- Fixtures: `backend/data/fixtures/insights_*.json` or generated local artifacts.

## Build
1. Add token comparison for aligned English, Hinglish and Hindi variants using the reference tokenizer.
2. Show request history from the shared store: text preview, language, selected route, cache status and token counts.
3. Add a cost estimator that separates reference token counts, provider-reported usage when available, and user-supplied price assumptions.
4. Train or load a lightweight output-length/cost estimate model (linear or ridge regression) on fixture data and display its predictions and error.
5. Add PCA or k-means summaries over request features from fixtures/history and visualise them with clear labels.
6. Present charts and tables that make the optimisation trade-offs easy to understand in a demo.

## Demo cases
- The same support question in English, Hinglish and Hindi.
- A history view showing cached, compressed and routed requests.
- A small cluster/PCA view with example requests for each group.

## ML/course angle
- Regression, PCA and clustering.
- Interpreting model outputs with simple evaluation metrics and visual summaries.

## Done when
- `/api/v1/insights/*` returns token comparisons and summary data.
- The page renders charts/tables without requiring live model calls.
- Fixture-backed tests or checks cover token counting and summary aggregation.