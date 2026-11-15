# Token Optimiser — team presentation guide

## Opening

“Token Optimiser is a CPU-first workbench for English, Hinglish and Hindi requests.
It brings answer reuse, prompt compression, model routing and token analytics into
one request pipeline. We show the actual decisions and their limits. Today's
default answers are authored fixtures, so the demonstration runs without a paid
provider or GPU.”

## Show the integrated application first

Start with `npm run dev` and open http://127.0.0.1:8080. Use the sequence in
[the demo runbook](docs/demo.md): cold Hinglish request, exact repeat, configuration
change, output controls, history, and Compression Studio handoff.

Explain the data flow while the execution trace is visible:

1. Lookup the original question in a configuration-specific cache.
2. On an accepted hit, reuse the answer and skip the remaining model path.
3. On a miss, execute the compression adapter and route using original features.
4. Return a labelled fixture or call the configured model with output controls.
5. Record provenance and usage once in SQLite.

The browser makes one `/api/v1/chat` request. The feature workspaces provide
detailed inspection around that shared lifecycle.

## Team contributions

| Presenter | Demonstration | ML / engineering explanation |
| --- | --- | --- |
| Tushar | Compression source/output view, CRF vs heuristic, phrase guards | Sequence tagging and guarded transformation; actual method and fallback |
| Rakesh | Policy thresholds, feature values, classifier comparison | Logistic regression, random forest, MLP; authored complexity labels |
| Shivam | Exact repeat, approximate candidate, saved-answer management | Normalization, nearest-neighbour retrieval, TTL and context isolation |
| Aman | Recorded history, output controls, token/cost scenarios | Ridge prediction, PCA and k-means; estimate and training-fit limitations |

## Explain evidence correctly

- **Local execution:** actual adapter outputs, reference counts, route decisions,
  cache events and this request's elapsed time.
- **Authored fixture:** default answers, routing labels, output-cap scenario
  examples and the insights training records.
- **Saved artifact:** versioned routing classifiers and metrics.
- **Historical research:** imported fingerprinted results shown in the compression
  evidence panel; a different evaluation from this running demo.
- **Live provider:** only after explicit server configuration and Studio selection;
  provider usage may be absent and prices are optional user assumptions.

Tokenization varies with text and encoding. Do not claim a universal Hindi token
multiplier, fixed output/input price ratio, millisecond service guarantee or fixed
percentage of end-to-end savings. Read the actual values displayed for the chosen
example. Reference token counts are not provider billing.

## Questions to be ready for

**Does compression preserve meaning?** Literal checks demonstrate exact phrase
retention. They do not establish semantic equivalence or answer correctness.

**What does routing accuracy measure?** Agreement with authored complexity labels.
It does not measure comparative answer quality of two live models. The saved MLP
also has a convergence limitation.

**Will similar questions always reuse a valid answer?** No. Changed conditions can
have high similarity. Approximate reuse is off by default in Studio, and the
matched question remains visible when inspected or deliberately enabled.

**What do output controls enforce?** Demo mode applies local formatting and a
reference-token limit. Live mode sends `max_tokens` and a format instruction to the
provider. Formatting and completeness are not guaranteed by an instruction.

**Are regression and clusters independently validated?** The ridge metrics describe
fit on authored training fixtures. PCA/k-means are exploratory and use neutral
cluster IDs. Neither establishes downstream utility.

**What changed since the report?** The branches are present in the merged history;
core orchestration, real Studio answering, cache short-circuiting, provider controls,
history provenance and the report's small-cap/fingerprint defects have been
addressed. See [the integration audit](docs/integration-audit.md). The original PDF
is a historical pre-merge assessment and has not been rewritten.

**What was verified?** Run the full backend suite, `npm run check`, and the offline
rehearsal. The browser smoke check covers real local feature calls, repeated reuse,
cache management, multilingual inputs, JSON output, history, handoff and mobile
layout. Provider behavior is checked with simulated HTTP responses; no paid call or
new answer-quality benchmark is claimed.

## Rehearse

```powershell
.venv\Scripts\python.exe scripts/check_pipeline.py
.venv\Scripts\python.exe -m pytest backend/tests -q
npm run check
npm run dev
```

Read [setup](docs/setup.md) for alternate ports and the optional live configuration.
