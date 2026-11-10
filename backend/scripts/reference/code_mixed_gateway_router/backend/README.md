# Code-Mixed Gateway — Backend

Hinglish (Hindi-English code-mixed) prompt compression + conformally-calibrated cascade
routing, exposed as an OpenAI-compatible `/v1/chat/completions` endpoint.

## Modules

| #   | Module                              | File                                                                | Verifies                                                                 |
| --- | ----------------------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| 1   | Data pipeline + tokenizer benchmark | `src/gateway/modules/m1_pipeline/`                                  | token counts across tokenizers, code-mix token inflation                 |
| 2   | Compressor                          | `src/gateway/modules/m2_compressor/`                                | trained LLMLingua-2 baseline (real when `.[compression]` installed) + heuristic/LLM, fail-closed re-injection |
| 3   | Conformal calibrator                | `src/gateway/modules/m3_conformal/`                                 | split-conformal error-bound threshold (Hoeffding LTT, grid 200)          |
| 4   | Cascade router                      | `src/gateway/modules/m4_router/`                                    | difficulty scoring + cheap/premium dispatch (pricing via `pricing.py`)   |
| 5   | FastAPI gateway                     | `src/gateway/modules/m5_gateway/`                                   | OpenAI-compatible `/v1/chat/completions`, streaming + `x_gateway` meta   |
| 6   | Telegram bot + SQLite               | `src/gateway/modules/m6_telegram/`                                  | webhook/polling bridge + cost-savings logging (secret via header)        |
| 7   | Evaluation suite                    | `src/gateway/modules/m7_eval/`                                      | Hinglish BLEU/ROUGE-L, token savings, span preservation, $/₹ cost        |
| 8   | Live dashboard                      | `src/gateway/modules/m8_dashboard/`                                 | `/v1/dashboard/*` endpoints + static HTML dashboard                      |
| 9   | Reasoning budget                    | `src/gateway/modules/m9_reasoning/`                                 | thinking-token budget estimator + Hinglish-vs-English delta              |
| 10  | Distill / reward                    | `src/gateway/modules/m10_train/`                                    | rejection-sampling distillation (CPU fallback) + task-correctness reward |
| 11  | Calibration + pricing               | `src/gateway/modules/m11_calibration/` + `pricing.py` + `config.py` | ECE/reliability, central pricing (single source `pricing.py`)            |
| 12  | Semantic similarity + gloss         | `src/gateway/modules/m12_semantic/`                                 | meaning-preserved similarity (`hash` offline / ST via `.[semantic]`), optional Hinglish→English gloss (`is_rule_based`) |

## Setup

```sh
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e ".[dev]"         # or: uv sync --extra dev
# optional: real tokenizers (tiktoken + HF Qwen/Llama/Gemma) for the fairness benchmark
pip install -e ".[tokenizers]"
```

Copy `.env.example` to `.env`. With `GATEWAY_DRY_RUN=true` (default) everything runs
offline with deterministic mocks — no API keys or GPUs required.

Optional: real LLMLingua-2 weights for the trained baseline (module 2):

```sh
pip install torch --index-url https://download.pytorch.org/whl/cpu  # Windows: CPU-only, skips the CUDA bundle
pip install -e ".[compression]"
# one-time ~700MB download of microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank
# on first use (cached under ~/.cache/huggingface)
```

Then `POST /v1/compress {"method": "llmlingua2"}` measures the real classifier,
`/v1/eval/curve` reports it with `is_simulated:false`, and
`GATEWAY_LLMLINGUA2=true` puts it in the live auto chain. Without the extra,
the same paths fall back to the heuristic and stay honestly labelled.

## Run

```sh
# gateway
uvicorn gateway.modules.m5_gateway.main:app --host 127.0.0.1 --port 8000
# or
cg-gateway
```

## Tests

```sh
pytest -q tests/test_m1.py   # then m2..m6
pytest -q tests/             # all
ruff check src tests
```

## Dashboard

`GET /dashboard` — self-contained HTML dashboard (no build step) backing onto
`/v1/dashboard/stats`, `/v1/dashboard/series`, `/v1/dashboard/recent`.

## Data

- `data/seed_hinglish.jsonl` — synthetic Hinglish seed (fluff + protected placeholders), committed.
- `data/benchmark.jsonl` — 50-row synthetic benchmark (heuristic compressed preview, `is_synthetic:true`), ignored.
- `data/calibration.jsonl` — 2000-row calibration (50 bench + 1950 pad synthetic), `is_real = bench_n>0`, ignored; synthetic defaults used if absent.
- `data/tokenizer_report.csv` — per-tokenizer token counts (written by module 1), ignored.
- `data/checkpoints/distilled.json` — 50-row distilled mapping (regenerate via `python -c "from gateway.modules.m10_train.distill import distill; distill(Path('data/benchmark.jsonl'), Path('data/checkpoints/distilled.json'))"`), ignored.
- `data/pilot.sqlite` — WAL-mode SQLite pilot log, ignored (`-shm/-wal` also ignored).

## Pricing

Single source `src/gateway/pricing.py` (`CHEAP_PER_1K_USD=0.00006`, `PREMIUM_PER_1K_USD=0.0025`, `FX_INR_PER_USD=83.5`, `PRICING_DATE=2026-08-28`). `config.py` and both `router.py` / `evaluate.py` import from there. Token counts are via `TokenCounter` (`tiktoken` if installed else whitespace) — costs are approximate and vary ~1.5× by tokenizer.

## Env & Proxy

- Backend: `GATEWAY_DRY_RUN=true` (offline mocks), `GATEWAY_PUBLIC_URL` for Telegram webhook loopback, `GATEWAY_TELEGRAM_WEBHOOK_SECRET` (not `token[-8:]` fallback) and `X-Telegram-Bot-Api-Secret-Token` header.
- Frontend: `VITE_GATEWAY_URL` — empty uses Vite proxy (`/v1,/dashboard,/healthz,/docs` → `127.0.0.1:8000` in dev); set to hosted origin in prod.
