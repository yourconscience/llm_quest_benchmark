# Architecture

## Overview
LLM Quest Benchmark evaluates how different agents complete Space Rangers `.qm` quests.
The runtime loop is:
1. Parse or step quest state via the TypeScript engine bridge.
2. Build an action prompt from current state and available choices.
3. Get agent choice (human/random/LLM).
4. Apply choice, log step, and detect outcome.
5. Persist run metrics and expose analysis.

## Main Runtime Layers

### 1. Quest Engine Layer
- `space-rangers-quest/`:
  TypeScript quest parser/player submodule.
- `llm_quest_benchmark/executors/ts_bridge/consoleplayer.ts`:
  Node entrypoint for parse/step execution.
- `llm_quest_benchmark/executors/ts_bridge/bridge.py`:
  Python subprocess bridge with startup preflight and actionable errors.

### 2. Environment Layer
- `llm_quest_benchmark/environments/qm.py`:
  Wraps bridge into Python environment semantics (`reset`, `step`, terminal detection).

### 3. Agent Layer
- `llm_quest_benchmark/agents/human_player.py`
- `llm_quest_benchmark/agents/random_agent.py`
- `llm_quest_benchmark/agents/llm_agent.py`

`LLMAgent` lazily initializes provider clients, so template rendering and agent construction do not require API keys.

### 4. LLM Provider Layer
- `llm_quest_benchmark/llm/client.py`:
  - provider/model normalization (`provider:model` + aliases)
  - adapters:
    - OpenAI
    - Anthropic
    - Google Gemini (OpenAI-compatible endpoint)
    - DeepSeek
  - shared retry/backoff and timeout handling
  - token/cost usage tracking per completion call

### 5. Execution and Analysis Layer
- `llm_quest_benchmark/core/runner.py`:
  Core quest run loop.
- `llm_quest_benchmark/core/analyzer.py`:
  Post-run analysis and benchmark summaries.
- `llm_quest_benchmark/core/benchmark_report.py`:
  Markdown report generator that joins benchmark artifacts with per-run summaries.
- `llm_quest_benchmark/executors/cli/commands.py`:
  CLI commands (`run`, `play`, `analyze`, `analyze-run`, `benchmark`, `benchmark-report`, `cleanup`, `server`).

### 6. Web Layer (Flask)
- `llm_quest_benchmark/web/app.py`:
  Flask app factory and blueprint registration.
- `llm_quest_benchmark/web/views/monitor.py`:
  Quest run UX and run state APIs.
- `llm_quest_benchmark/web/views/benchmark.py`:
  Benchmark execution UX.
- `llm_quest_benchmark/web/views/analyze.py`:
  Dashboard and run analytics views.
- `llm_quest_benchmark/web/models/database.py`:
  Includes `RunEvent` table for structured live step telemetry.

## Persistence
- `metrics.db`:
  Benchmark/run metrics for CLI workflows.
- `instance/llm_quest.sqlite`:
  Flask web run/step/event records.
- `results/<agent>/<quest>/run_<id>/run_summary.json`:
  Compact step trace + per-step decisions + aggregated token/cost usage.

## Configuration
- `.env` (copied from `.env.template`):
  Provider API keys and optional per-model pricing overrides.
- `configs/`:
  Benchmark YAML configs.

## Operational Notes
- Bridge and quest execution logic remain TypeScript-first; Python orchestrates and validates.
- Flask is the canonical web interface.
- Non-local deployment guidance is in `docs/DEPLOYMENT.md`.
