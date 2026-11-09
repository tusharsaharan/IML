# Cache runtime

`POST /api/v1/cache/answer` is the cache-aside entry point for a platform request. It first checks the cache. On a miss it calls the configured `Provider`, then automatically saves reusable answers for later exact or similar questions.

```json
{"text":"Campus internet login page will not open","language":"auto"}
```

The response reports whether it reused an answer, generated one, and stored it. `source` values distinguish authored demo fixtures from live-provider output. The generic demo fallback is never learned. In live mode, an answer is stored only after the configured OpenAI-compatible provider returns successfully.

## Storage and limits

- SQLite is the durable source of truth and works offline without another service.
- Automatically learned entries expire after 30 days by default. The cache evicts least recently used entries when it reaches its configured maximum.
- Set `IML_CACHE_TTL_SECONDS`, `IML_CACHE_MAX_ENTRIES` and `IML_CACHE_SEMANTIC_THRESHOLD` in the server `.env` to tune expiry, capacity and near-match strictness.
- Entries, exact keys and lookup counters are partitioned by `X-Cache-Scope`. The demo creates a browser-local scope. In production, strip any client-provided scope header and set it from a verified account or tenant claim at the trusted gateway.
- Redis or Valkey can optionally act as a hot index for exact matches. Install `python -m pip install -e "backend[cache-redis]"` and set `IML_CACHE_REDIS_URL=redis://127.0.0.1:6379/0`. If Redis is unavailable, requests fall back to SQLite.
- Redis is an accelerator in this implementation; SQLite remains authoritative. A multi-instance deployment must give all instances a shared durable cache repository before relying on shared automatic answers.

## Reuse and privacy

Exact matches normalize case, punctuation and whitespace. Near matches use the existing offline hashed word and character n-gram vectors, with a small Hinglish-to-English vocabulary bridge. Entry vectors are saved once and compared as a NumPy matrix on lookup, avoiding repeated embedding work for every candidate. Scores are similarity signals, not proof of equivalent meaning. Review the matched question and tune `IML_CACHE_SEMANTIC_THRESHOLD` against a labelled query set before enabling broad semantic reuse.

Automatic writes skip obvious email addresses, URLs, long numeric identifiers, common account/secret markers, and generic demo fallbacks. These checks are conservative filters, not a substitute for a full privacy classifier. This course app has no user authentication; the browser scope is not an authorization boundary. Do not cache personal, account-specific, or confidential prompts until trusted authentication and privacy controls are deployed.

Demo FAQ seeding is optional. It adds authored examples to try the retrieval page. During normal use, eligible answers produced by the platform are learned automatically through `/answer`.
