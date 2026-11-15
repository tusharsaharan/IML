# API contracts

All features return JSON. Shared request metadata is attached by the core pipeline.

## Core
- `GET /api/v1/health` — service status and demo/live mode.
- `POST /api/v1/chat` — run the selected pipeline over a user request.

`/api/v1/chat` request:
```json
{"text":"Yaar basically mera hostel ka wifi slow hai", "language":"auto", "mode":"demo", "compression":{"enabled":true,"method":"crf","budget":0.6,"protected_phrases":[]}, "routing":{"enabled":true,"policy":"balanced"}, "cache":{"enabled":true,"accept_semantic":false}, "output":{"format_constraint":null,"max_tokens":120}, "compare":false}
```

Text must contain letters/numbers and be at most 4,000 characters (the compression
workspace independently accepts 12,000). Language choices are `auto`, `en`,
`hinglish`, `hi`; modes are `demo`, `live`. Defaults are authored demo, enabled
heuristic compression at 0.6, balanced routing, enabled exact reuse and a 120-token
output cap. Protected phrases use the existing compression validation. Unknown
fields are rejected. `compare` is retained as `false` for exported requests;
counterfactual provider comparison is not implemented and `true` is rejected.

`output.max_tokens`: integer 1–4096. `format_constraint`: null, `3 bullets`,
`JSON only`, or `no preamble`. Live calls forward these controls to the provider.
Demo answers are formatted/truncated locally using the active reference counter;
the response labels this behavior. An exact punctuation/operator comparison is
required in addition to the cache's normalization. Approximate candidates are not
automatically accepted unless `accept_semantic` is explicitly true.

Optional `X-Cache-Scope` provides local demo separation (1–128 letters, numbers,
colons, underscores or hyphens). Core derives a configuration-specific hashed
scope, returned as `cache.scope`; pass that value to the cache-management APIs to
inspect/delete those entries. Scope headers are not authentication. Demo and live
entries never share a pipeline context.

Successful responses contain:

| Field | Meaning |
| --- | --- |
| `request_id`, `elapsed_ms`, `mode`, `language` | Server execution identity, elapsed processing time and effective language |
| `answer`, `answer_source`, `origin_source`, `model`, `provider_called` | Final text, fixture/cache/live provenance and actual provider-call status |
| `trace` | Ordered cache, compression, routing, generation and insights stages with completed/hit/miss/skipped statuses |
| `cache` | Accepted hit, candidate hit, match type, score, matched question, scope and learning outcome |
| `compression`, `routing`, `prediction` | Actual feature results; null for skipped stages |
| `output` | Requested controls, local demo truncation and execution note |
| `usage` | Reference original/prompt/sent/answer counts, tokenizer backend and separately nullable provider usage |
| `cost` | Nullable USD calculation and basis; zero with `no_provider_call` for demo/cache |

Each successful pipeline execution is recorded once. On cache hits, reference
input sent is zero and provider usage remains null: the previous generation's
usage is not billed to the repeat. Missing live usage/prices stay unknown. Price
calculations use configured USD-per-million assumptions, not fixed catalog rates.

Errors: `422` invalid request; `503` live mode not fully configured; `502` provider
HTTP/invalid-answer failure; `504` provider timeout. Provider errors do not produce
an authored success answer or a successful history/cache write. Live mode requires
server `IML_MODE=live`, endpoint/key and both non-demo model IDs. Request mode
defaults to demo even on a live-configured server.

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
