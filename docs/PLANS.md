# Plans

## Current Direction
Keep the existing Flask web app as the primary UI and harden the full experiment workflow around it.

## Experiment Loop Status (February 15, 2026)
1. Baseline matrix `CLI_benchmark_20260214_235403` (reasoning prompt): 2/24 success.
2. Creative matrix `CLI_benchmark_20260215_000103` (consequence scan): 2/24 success.
3. Creative matrix `CLI_benchmark_20260215_000925` (objective guard + completion system): 2/24 success.
4. Provider-tuned matrix `CLI_benchmark_20260215_002034` (best-known prompt per provider): 3/24 success with lower token/cost footprint.
5. Current pattern:
   - `consequence_scan` improved Claude and Gemini on `Boat`.
   - DeepSeek regressed under both creative variants.
   - GPT-5-mini remains latency-unstable due frequent empty visible outputs/retries.
6. Reporting artifact:
   - `results/benchmarks/report_provider_matrix.md` contains per-model outcomes, token/cost totals, and failure decision highlights.

## Phase 1: Runtime and Reliability
1. Keep TypeScript bridge behavior unchanged, but preserve strong startup diagnostics.
2. Validate environment setup with reproducible smoke checks (`CLI`, `bridge parse`, `random run`).
3. Ensure `.env` loading is automatic for CLI and Flask paths.
4. Finalize timeout semantics so benchmark outcome, DB run outcome, and JSON summary stay strictly aligned.

## Phase 2: Model/Provider Coverage
1. Maintain current provider support:
   - OpenAI
   - Anthropic
   - Google Gemini
   - DeepSeek
2. Keep provider model list current and visible in Flask model selector.
3. Add/maintain unit tests for provider parsing and client selection.
4. Add provider-specific behavior knobs in config (for example: force numeric retry mode for GPT-5 family).

## Phase 3: Experiment Workflow Hardening
1. Make it easy to run a matrix of:
   - quest set
   - model/provider
   - prompt template
   - temperature
2. Keep all run logs and analysis artifacts queryable from CLI and Flask dashboard.
3. Add regression checks for:
   - bridge startup
   - non-LLM smoke run
   - web quest init/run/step endpoints
4. Standardize prompt-iteration loop:
   - run matrix
   - generate `benchmark-report`
   - inspect failure highlights
   - apply prompt/config deltas
   - rerun matrix

## Phase 4: Deployment
1. Publish Flask app with stable custom domain (replace random free ngrok URL).
2. Prefer Cloudflare Tunnel + domain routing for low-ops exposure.
3. Keep alternatives documented (`Fly.io`, `Render`) for managed hosting.

## Documentation Quality
1. Keep `README.md`, `AGENTS.md`, and files in `docs/` aligned with current code behavior.
2. Use the global `doc-gardening` skill scanner before releases.
   - Quick command: `./scripts/doc_gardening.sh`
   - Shortcut trigger in chat: `/doc-gardening`
3. Open doc-only fix PRs for stale commands, paths, and architecture claims.
4. Keep experiment notes under `docs/experiments/` with one file per iteration batch.

## Later (Not ASAP)
1. Optional live debug stream in web UI during runs (terminal-grade trace visibility in browser).
2. Add token/cost trends to web analytics pages.
3. Add curated per-provider prompt presets selected by benchmark evidence.
