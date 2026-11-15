# Merge and pipeline integration audit

Reviewed on 15 November 2026 against local `main` at `3390095`, using the user's pre-merge `main_iml.pdf` as reference evidence. The report was treated as material to assess, not as an instruction source. No fetch, push, history rewrite, live provider call, Kaggle job or research-compressor change was performed.

## Git merge assessment

The working tree was clean at the start. The local tracking tips `origin/aman` (`19c53a4`), `origin/rakesh/routing` (`97751c3`) and `origin/shivam-kumar` (`cec558f`) are all ancestors of `main`. The three integration merge commits are `184b739`, `2161ddc` and `3390095`. These observations establish ancestry against locally available refs; remote branches were not refreshed.

All four feature APIs, pages, tests, routing artifacts, newer compression phrase guards and pinned source manifests are present. Git ancestry alone did not establish functional integration: the merged Studio still called independent endpoints without an answer-generation lifecycle.

## Findings and changes

| Finding | Resolution |
| --- | --- |
| Documented `/api/v1/chat` had no implementation | Core now owns validation, lookup, compression, routing, answer generation, eligible learning and history |
| Browser continued after cache hits and never generated a final answer | Studio now makes one chat call; accepted hits skip compression/routing/generation |
| Browser hid feature failures and supplied fabricated token/cost fallback values | Results come from server execution; validation/provider failures remain visible |
| Shared settings ignored documented `IML_` environment names | Added the prefix and handling for blank optional prices/model defaults |
| Output controls only influenced estimates | Live calls receive actual `max_tokens` and format instructions; demo formatting/reference caps are labelled local operations |
| Cache key omitted pipeline configuration | Context includes mode, original language setting, models, endpoint, transformations, policy, output instructions and version |
| Similarity could automatically reuse changed-detail questions | Approximate reuse is opt-in in the integrated pipeline; candidate question/score remain inspectable |
| Exact normalization drops punctuation/operators | Pipeline adds a stricter whitespace/case comparison before accepting an exact reuse |
| Compression handoff only downloaded JSON | Checked output can now be loaded into Studio without a second compression pass |
| History invented output defaults and replaced recorded zero input | History preserves zero/missing values and exposes answer provenance and provider usage |
| Cost estimate could exceed caps below ten | Bounds now respect caps from one token and cannot create negative savings from the old floor |
| Regression could predict a negative capped length | Predictions are bounded below by one |
| Cluster names claimed unvalidated semantics | Cluster names are neutral numbered IDs; actual cheap/strong routes enter the feature mapping |
| LF checkouts failed two pinned-source checks | Verify exact bytes or only a newline conversion that matches the original hash; binaries stay exact |
| Setup retrained and rewrote saved artifacts on every run | Reuse committed artifacts; retraining is explicit or triggered by missing artifacts |
| Cache SQLite context managers committed without closing | Cache connections now close after each operation |
| Existing tests wrote into the presentation database | An automatic fixture isolates test storage; rehearsal uses disposable data |

## Verification

The full backend suite, frontend check, offline rehearsal and real-browser scenarios are run for this integration. The browser check exercises the actual local backend, not mocked successful feature responses. Provider tests use an in-process mock transport; they verify payload/usage/failure behavior without calling a paid service.

The original merged suite reproduced the report's two LF/CRLF fingerprint failures. The verification change does not bless arbitrary normalized content: a candidate must match the existing manifest hash after the allowed transport conversion. New tests reject content changes and binary normalization. Imported source files, manifests and weights remain unchanged.

Observed verification results:

| Check | Result |
| --- | --- |
| Full merged backend suite | 289 passed |
| Final targeted pipeline/cache checks, including normalized-key collision handling | 80 passed |
| Frontend `npm run check` | TypeScript, 57 Vitest cases and production build passed |
| Disposable offline rehearsal | English, Hinglish and Hindi cold requests plus exact repeats passed |
| Edge browser smoke check | Real API cold/repeat flow, cache deletion, language presets, JSON cap, history and handoff passed |
| Mobile / error path | 390px layout without horizontal overflow; explicit QA-only 503 displayed; no JavaScript page errors |
| Targeted Ruff and Git whitespace checks | Passed |

Non-failing tooling notices remain: the installed FastAPI/Starlette test client
emits a deprecation warning, and Vite reports a large JavaScript chunk. These are
not performance or production-readiness measurements. Screenshots are saved under
ignored `test-results/pipeline/`. The browser script is optional and uses an
already installed Playwright package and Edge; it does not download a browser.

## Boundaries retained

- Demo answers are authored fixtures, including general support guidance and a labelled unknown-topic fallback. There is no arbitrary offline LLM or translation service.
- Routing labels describe authored complexity categories, not observed economy/strong-model answer success. Saved metrics are retained, including convergence limitations.
- Prompt compression and literal checks do not establish semantic equivalence. No research algorithm or checkpoint was changed.
- A generation cap is forwarded to the provider; its reference tokenization and format compliance may differ. The app does not invent counterfactual completion savings.
- Health checks configuration readiness, not external service reachability.
- Scope headers are not authentication. Optional Redis, local embedding extras, production concurrency, load, capacity and independent quality evaluation are not certified by these checks.
- The original PDF remains a historical pre-merge audit. Its missing-orchestration and cap-defect descriptions now need this addendum when presented with the updated application.
