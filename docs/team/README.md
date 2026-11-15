# Team workstreams

All four workstreams are independent. Use the contracts in `contracts/api.md` and the fixtures in `backend/data/fixtures/`.

| Member | Area | Main files | API |
|---|---|---|---|
| Tushar | Compression Studio | `src/features/compression`, `backend/src/gateway/features/compression` | `/api/v1/compression/*` |
| Rakesh | Smart Router | `src/features/routing`, `backend/src/gateway/features/routing` | `/api/v1/routing/*` |
| Shivam | Memory & Cache | `src/features/cache`, `backend/src/gateway/features/cache` | `/api/v1/cache/*` |
| Aman | Token & Cost Insights | `src/features/insights`, `backend/src/gateway/features/insights` | `/api/v1/insights/*` |

Shared changes (`src/components`, `src/lib`, `backend/src/gateway/core`, contracts) require coordination.

## Merged application integration — 2026-11-15

The user requested a coordinated audit/integration of all merged workstreams.
Core owns the shared `/api/v1/chat` lifecycle, and `src/lib/pipeline.ts` owns its
browser contract. The Studio consumes one core response; feature adapters retain
their own implementations and do not import another feature. Compression hands
checked output to Studio with compression disabled. Cache management accepts the
pipeline's returned scope. Insights reads server-recorded provenance and usage.
See `docs/integration-audit.md` and `contracts/api.md` for the reconciled contract.

Each person should finish with: a working page, working API, visible ML or algorithmic logic, three demo cases, targeted tests, and their report/poster section.
