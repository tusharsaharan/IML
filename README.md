# Token Optimiser

An application workbench for exploring prompt compression, model routing and answer reuse across English, Hinglish and Hindi requests.

## Quick start

```bash
python scripts/setup.py
npm run dev
```

Open `http://localhost:8080`.

## Structure

- `src/features/*` — independently owned application pages.
- `backend/src/gateway/features/*` — independently owned feature APIs.
- `backend/src/gateway/core/` — shared request pipeline, providers and storage.
- `backend/src/gateway/modules/` — reusable imported implementation.
- `contracts/` — request/response contracts shared by all features.
- `docs/team/` — implementation sheets for each team member.

## Configuration

Copy `.env.example` to `.env`. Demo mode runs with authored fixtures and local utilities. Live mode requires an OpenAI-compatible endpoint and model IDs. API keys stay on the server.