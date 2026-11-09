# IML: application-first Token Optimiser

Deliver a usable CPU-first course application. Reuse the imported Research code through feature adapters. Keep observed results, authored demo data and live calls distinguishable.

## Ownership
- Tushar: `src/features/compression`, `backend/src/gateway/features/compression`, compression scripts/tests.
- Rakesh: `src/features/routing`, `backend/src/gateway/features/routing`, routing scripts/tests.
- Shivam: `src/features/cache`, `backend/src/gateway/features/cache`, cache scripts/tests.
- Aman: `src/features/insights`, `backend/src/gateway/features/insights`, insight fixtures/tests.
- Shared foundation: `src/components`, `src/lib`, `backend/src/gateway/core`, contracts and configuration. Coordinate interface changes before editing these.

Read your task sheet in `docs/team/` first. Each feature owns its API, page and tests. Features may import core utilities but must not import another feature. The core pipeline integrates them.

## Working rules
- Use the existing React/Vite and FastAPI structure. Keep models optional and CPU-runnable.
- No new paid services, background GPU jobs or automatic model downloads.
- API keys stay server-side in the ignored `.env`.
- Do not relabel authored routing labels as measured model correctness, similarity as semantic equivalence, or reference token counts as provider billing.
- Default demo answers are authored fixtures; arbitrary live answers need a configured endpoint.
- Keep imported source attribution. Changes to imported files need an entry in `docs/source-attribution.md`.
- Run targeted backend tests plus `npm run check` for relevant frontend changes. No subagents unless the user explicitly requests them.
- Preserve unrelated edits. Do not push or rewrite published git history unless asked.
