# API contracts

All features return JSON. Shared request metadata is attached by the core pipeline.

## Core
- `GET /api/v1/health` — service status and demo/live mode.
- `POST /api/v1/chat` — run the selected pipeline over a user request.

`/api/v1/chat` request:
```json
{"text":"...", "language":"auto|en|hinglish|hi", "mode":"demo|live", "compression":{"enabled":true,"method":"heuristic|crf","budget":0.6}, "routing":{"enabled":true,"policy":"economy|balanced|quality"}, "cache":{"enabled":true}, "compare":false}
```

## Compression
- `POST /api/v1/compression/analyze`
- request: `{ "text": "...", "method": "heuristic|crf", "budget": 0.6 }`
- response: original/compressed text, token counts, removed spans, protected spans, method, notes.

## Routing
- `POST /api/v1/routing/predict`
- request: `{ "text": "...", "compressed_text": "...", "policy": "economy|balanced|quality" }`
- response: selected tier/model, features, model scores, explanation, authored/demo label.

## Cache
- `POST /api/v1/cache/lookup`
- request: `{ "text": "...", "language": "auto" }`
- response: hit, match type, similarity, matched question, answer source, cache id.

## Insights
- `POST /api/v1/insights/record` — store a pipeline result.
- `GET /api/v1/insights/summary` — aggregate counts, token/cost history and simple model outputs.
- `POST /api/v1/insights/tokenize` — compare token counts across languages/models.