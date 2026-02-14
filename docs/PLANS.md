# Plans

## Current Direction
Keep the existing Flask web app as the primary UI and harden the full experiment workflow around it.

## Phase 1: Runtime and Reliability
1. Keep TypeScript bridge behavior unchanged, but preserve strong startup diagnostics.
2. Validate environment setup with reproducible smoke checks (`CLI`, `bridge parse`, `random run`).
3. Ensure `.env` loading is automatic for CLI and Flask paths.

## Phase 2: Model/Provider Coverage
1. Maintain current provider support:
   - OpenAI
   - Anthropic
   - Google Gemini
   - DeepSeek
   - OpenRouter (optional gateway)
2. Keep provider model list current and visible in Flask model selector.
3. Add/maintain unit tests for provider parsing and client selection.

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
4. Improve timeout semantics so benchmark outcomes and DB outcomes stay consistent under long-running LLM calls.

## Phase 4: Deployment
1. Publish Flask app with stable custom domain (replace random free ngrok URL).
2. Prefer Cloudflare Tunnel + domain routing for low-ops exposure.
3. Keep alternatives documented (`Fly.io`, `Render`) for managed hosting.

## Documentation Quality
1. Keep `README.md`, `AGENTS.md`, and files in `docs/` aligned with current code behavior.
2. Use the `skills/doc-gardening` scanner before releases.
3. Open doc-only fix PRs for stale commands, paths, and architecture claims.

## Later (Not ASAP)
1. Optional live debug stream in web UI during runs (terminal-grade trace visibility in browser).
2. Token/cost accounting per run and per step for all providers.
