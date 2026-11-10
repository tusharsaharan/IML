# Router-RL track (FREE-ONLY) — runbook

Free tier mapping (no money): `cheap=llama-3.1-8b-instant`, `premium-proxy=llama-3.3-70b-versatile`, both on Groq free key. Claim proxy numbers only.

## Order (linear, no loops)

1. `colab_00_audit.ipynb` (CPU) → `query_list.json`, `DECISION_00.json`, `fig00_audit.png`
2. `colab_01_label.ipynb` (Groq free) → `groq_labels.jsonl`, `calibration_real.jsonl`, `splits.json`, `human_check.csv`, `DECISION_01.json`
3. **MANUAL:** fill `human_check.csv:human_ok` (y/n, ≥100 rows), re-upload to Drive
4. `colab_02_supervised.ipynb` (T4) → `logreg.pkl`, `xgb.json`, `DECISION_02.json`
5. `colab_03_bandit_rl.ipynb` (T4) → `bandit_head.pt`, `DECISION_03.json`
6. `colab_04_conformal_safe.ipynb` (CPU) → `thresholds.json`, `DECISION_04.json`
7. `colab_05_eval.ipynb` (CPU, test touched ONCE) → `eval_report.json`, `fig05_pareto.png`, `DECISION_05.json`
8. Copy back to `backend/data/`: `calibration_real.jsonl`, `thresholds.json`, `eval_report.json`, `splits.json`
9. `python backend/scripts/freeze_splits.py --check` must print OK

## Anti-spin gates

- Each notebook asserts previous `DECISION_*.json` hash; abort on mismatch.
- Splits frozen seed 42; test IDs sealed until NB05.
- After NB05: no retraining. New ideas → Future Work section.

## Repo glue (already scaffolded)

- `src/gateway/modules/m4_router/learned_policy.py` — `LearnedScorer` (heuristic fallback, no artifacts needed for tests).
- `data/calibration_real.schema.json` — row validator for NB01 output.
- `scripts/freeze_splits.py` — local freeze/check.

## Colab secrets needed

- `GROQ_KEY` (free, console.groq.com). No OpenAI key. HF token optional.
