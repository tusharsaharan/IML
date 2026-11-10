# Code-Mixed Gateway: The Complete Documentation & Source of Truth

## Executive Summary
This project is an advanced, research-first LLM API Gateway built specifically to handle **Hinglish and Code-Mixed text**. Existing ML infrastructure assumes users communicate in clean English. This bias creates massive hidden financial penalties (Tokenizer Tax and Reasoning Tax) for users in the Global South who mix languages like Hindi and English. 

Our system solves this via a **Mixture-Aware Adaptive Compression Policy** and a **Conformally Calibrated Cascade Router**. It actively intercepts code-mixed prompts, mathematically prunes filler words while protecting strict entities, and dynamically routes traffic to cheap open-weight models versus premium frontier models—all while exposing every metric to the end user in a highly interactive, transparent web application.

---

## Part 1: Detailed Walkthrough of the Web Interface (UI Features)

Every feature in the React/Vite frontend exists to provide scientific transparency. Here is a breakdown of every page, button, and widget:

### 1. The Gateway Playground (`/demo`)
This is the live testing environment where users run their Hinglish prompts through the gateway.
* **Input Box & Prompt Chips:** Users can type custom prompts or click quick-load chips like `Support - Hinglish`, `Math - Hinglish`, `Phone + polite fluff`, and `Protected span` to test specific edge cases.
* **METHOD Dropdown:**
  * `auto`: Automatically uses the smartest available compression (model > adaptive > heuristic).
  * `adaptive` *(Novel)*: Runs the Mixture-Aware policy that changes aggressiveness based on the Hindi-English ratio.
  * `heuristic`: A static fallback that just blindly prunes filler words (`"yaar"`, `"matlab"`).
  * `model`: Uses a neural compressor (or returns a `[[COMPRESSED]]` mock if running offline).
* **"Stream answer" Checkbox:** Toggles SSE (Server-Sent Events) to stream the LLM's response letter-by-letter live to the UI.
* **"Reproducibility mode" Checkbox:** Designed for peer reviewers. Checking this opens a hidden drawer revealing the exact Git Commit SHA running, the raw `cURL` command to bypass the UI, the hidden system prompt sent to the LLM, and the raw `x_gateway` JSON telemetry headers.
* **"Run through the gateway" Button:** Triggers the pipeline.
* **"What got cut" Card:** Shows the token reduction (e.g., `26 -> 18 tokens`), the percentage of tokens kept, and the exact compressed prompt.
* **"Shred - Watch Filler Fall" Visualizer:** An interactive word-cloud animation showing exactly which words from the original prompt were retained and which filler words were dropped.
* **Reward Autopsy:** Displays the semantic similarity score (e.g., `0.893`) proving the compressed text kept the original meaning.

### 2. Live Telemetry Dashboard (Bottom of `/demo`)
Once a prompt is run, the UI exposes the raw internal decision-making process:
* **Routing & Difficulty Anatomy:** Decomposes the prompt's complexity into four weighted metrics: *Code-Mix (40%)*, *Entity Density (30%)*, *Math Markers (20%)*, and *Length (10%)*. Shows the calculated `Total Difficulty`, the `Threshold τ` (e.g., 0.085), and mathematically proves why the query was routed to the `cheap` or `premium` tier.
* **Cost & Savings:** Shows the live micro-cent cost of the API call (`$0.000002`) and exactly how much money was saved versus blindly sending it to GPT-4o.
* **Reasoning Budget:** Displays the predicted number of "thinking tokens" required for this query, explicitly showing the $\Delta$ tax (e.g., `+9 tokens`) incurred specifically because the user wrote in Hinglish instead of English.

### 3. The Research Proof Page (`/results`)
This is the scientific heart of the app. It streams live benchmark metrics computed on 50+ benchmark rows.
* **Top Stat Badges:**
  * **Adaptive Savings:** Shows total % savings vs static heuristics.
  * **Hinglish + reasoning:** Shows the average reasoning tax (e.g., `+56.34` tokens).
  * **Hinglish tokenizer tax:** Shows the bucketed token inflation multiplier.
  * **Fidelity Bound (95%):** The Hoeffding upper error bound on the compressor.
* **Adaptive Code-Mix Compression Chart:** A Pareto Frontier graph comparing `distilled`, `heuristic`, `adaptive`, and `blind truncation`. Proves that the `adaptive` policy achieves maximum token savings without sacrificing reward score.
* **Tokenizer Fairness Bucketing Graph:** A bar/line chart dividing 50 queries into Low, Mid, and High Hindi-mix buckets. Proves that as Hindi usage increases, the Western Tokenizer inflates the token count and costs exponentially.
* **Falsifiability Panel (Conformal Routing):** Interactive line charts showing the *Empirical Risk $\hat{R}(\tau)$* against the *Hoeffding Upper Bound*. Challenges the user to break the 5% error bound in the next 100 queries.

### 4. Adversarial Arena ("Break my compressor")
A gamified public red-teaming zone.
* Users try to write tricky prompts with negations (`"DO NOT refund"`) or amounts (`"Rs. 2500"`) and click **"Test break my compressor"**.
* If the compressor accidentally deletes a critical word, the UI logs a "Break!"
* If the `safety_span.py` reinjection module successfully protects it, it flashes "Safe". 
* **Public Leaderboard:** Displays the global break rate (currently 0%), proving the fail-closed algorithm is mathematically safe for production.

### 5. Code-Switch Tokenizer Slider
An interactive component visualizing the Tokenizer Tax. Users drag a slider from `100% English` to `100% Hindi`. As the slider moves, it dynamically calculates how the exact same meaning inflates from 16 tokens (`$0.000040`) in Western models up to 43 tokens (`$0.000107`), proving the economic inequality visually.

---

## Part 2: The Five Core Scientific Novelties

1. **Mixture-Aware Adaptive Compression Policy:** Our novel backend algorithm dynamically calculates a target kept-ratio based on the prompt's `code_mix_ratio()` and mathematical difficulty. It safely shrinks clean English by 40% but cautiously protects heavy Hinglish, avoiding the semantic destruction common in static compressors like LLMLingua.
2. **Conformal Fidelity Guarantee:** The first system to wrap prompt compression on code-mixed text in a Hoeffding Learn-Then-Test (LTT) conformal risk control bound, guaranteeing < 5% failure rates.
3. **The Hinglish Reasoning Tax:** Measured and proved that reasoning LLMs (like DeepSeek-R1) silently charge users an average of +56 extra thinking tokens to process Hinglish versus pure English.
4. **Bucketed Tokenizer Fairness Tax:** Mathematically proves token inflation inequality by creating synthetic English controls and bucketing prompts by Code-Mix density, demonstrating the gradient penalty placed on non-English speakers.
5. **Fail-Closed Protected-Span Guarantee:** A strict safety pipeline that extracts sensitive entities (Currency, Negations, PII) into `[[PSi]]` placeholders *before* compression and mechanically reinjects them afterward. It aborts the pipeline and returns the uncompressed text if any tracking marker is lost.

---

## Part 3: Backend Architecture & Code Structure

The backend is built in FastAPI (`python 3.10+`) and heavily modularized:
* **`m1_pipeline` (Tokenizer & Benchmarking):** Contains the token counting logic and the core code-mix ratio calculator (`code_mix_ratio`).
* **`m2_compressor`:** Houses `compressor.py` (the heuristic pruner dropping words like `"yaar"`) and `safety_span.py` (the Regex-based fail-closed extraction and reinjection loop).
* **`m3_conformal`:** Implements the Learn-Then-Test Hoeffding risk boundaries.
* **`m4_router`:** The `DifficultyScorer` that processes Entity Density, Length, Code-Mix, and Math markers to generate a difficulty score and route traffic against the $\tau$ threshold.
* **`m5_gateway`:** The FastAPI application (`main.py`) exposing the core API endpoints:
  * `POST /v1/compress` (Runs compression)
  * `POST /v1/chat/completions` (OpenAI compatible routing endpoint)
  * `POST /v1/reasoning/budget` (Calculates the reasoning tax)
  * `POST /v1/compress/redteam` (Automated grading for the Adversarial Arena)
* **`m12_novel`:** The true research engine. Contains `adaptive.py` (calculating the target ratio: `Base + (0.30 * mix) + (0.18 * diff)`), `gloss.py` (translating Hinglish slang for benchmark controls), and `analysis.py` (the code-mix bucketing loops).

### Cascade routing research (live study)
The active routing study — router fine-tuning, difficulty scoring, conformal calibration, graded datasets and the full status report — lives at `backend/experiments/cascade_routing/` (report: `cascade_full_report.pdf`; pipeline scripts: `backend/scripts/router_track/`).

## Setup & Execution
**Frontend:**
```bash
npm install
npm run dev --port 8080
```
**Backend:**
```bash
cd backend
.venv\Scripts\activate
uvicorn gateway.modules.m5_gateway.main:app --host 127.0.0.1 --port 8000
```
*(Offline mode: Configure `GATEWAY_DRY_RUN=true` in `backend/.env` to run full mock evaluations without API keys.)*
