# Integrated demo runbook

## Prepare

Run `python scripts/setup.py`, then `npm run dev`. Keep the terminal open and visit http://127.0.0.1:8080. Use authored demo mode for a presentation that requires no external provider. Run `.venv\Scripts\python.exe scripts/check_pipeline.py` beforehand; its database is disposable.

## Present the single pipeline

1. **Cold request:** choose Hinglish support. Keep cache, CRF and routing enabled. Run the pipeline. Explain that the trace comes from one server execution. Show actual method, original/compressed reference counts, route score, threshold and authored answer label.
2. **Repeat:** use Repeat this request. The cache returns the saved answer. Compression, routing and generation are explicitly skipped. Reference input sent is zero and no new provider usage is attributed to this request.
3. **Control the stages:** disable cache to force a fresh run. Switch economy/balanced/quality and inspect thresholds. A policy change need not change the selected tier. Toggle compression to compare the prompt path; this is not a controlled answer-quality experiment.
4. **Output controls:** choose JSON only and a cap such as 40. In demo mode formatting/capping is local and labelled. Show the truncation notice if present. In configured live mode these controls are sent to the provider; format compliance is not guaranteed.
5. **Audit:** open View request history. Find the recorded language, actual route and answer source. Fixture baseline rows remain labelled separately. Use Manage this pipeline cache to inspect/delete its saved answer; return to Studio to demonstrate a new miss.
6. **Compression handoff:** open Compression, analyze a preset and optionally protect a phrase. Click Send to Request Studio. The final checked output becomes the Studio input and compression is disabled. Run it to finish the answer lifecycle.

Repeat the cold/repeat sequence with English library and Hindi assignment. Hindi inputs currently select English authored support answers; this is fixture retrieval, not multilingual generation.

## Explain the cache limitation

Approximate reuse is disabled by default. After a library question has been saved, a lost-book variant may be a high-similarity candidate but is not automatically reused. The default pipeline proceeds to its labelled answer path. Its authored library fixture is general guidance and still cannot resolve the lost-book condition. If approximate reuse is enabled deliberately, inspect the matched question before trusting an answer.

Cache entries are separated by configuration and a local browser scope. These scopes are demonstration separation, not authenticated access control. The independent Cache workspace also offers its original cache-only FAQ lab; it is distinct from the integrated Studio flow.

## If something fails during the presentation

- Backend unavailable: restart `npm run dev`; wait for both services to start.
- Port occupied: use the alternate-port commands in `docs/setup.md`.
- Provider unavailable: show the visible error or explicitly select authored demo mode. There is no silent provider-to-fixture success fallback in `/chat`.
- Trained method unavailable: show the labelled fallback and inspect the relevant feature page.
- Warm cache when you wanted a cold run: disable cache or delete entries using the result's cache-management link.

Do not claim a fixed percentage of end-to-end savings, semantic preservation, measured model correctness or provider billing from reference counts. The application provides inspectable behavior; independent answer-quality and load evaluation remain separate work.
