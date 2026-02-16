# LLM Quest Benchmark Repository Guide

## Purpose
This repository benchmarks how human and LLM agents solve Space Rangers text quests (`.qm` files).

## Main Components
- `llm_quest_benchmark/environments/`:
  Quest environment layer backed by the TypeScript engine bridge.
- `llm_quest_benchmark/executors/ts_bridge/`:
  Python ↔ TypeScript bridge (`bridge.py`, `consoleplayer.ts`) over `space-rangers-quest`.
- `llm_quest_benchmark/agents/`:
  Human, random, and LLM agents.
- `llm_quest_benchmark/llm/`:
  Provider-aware client adapters (OpenAI, Anthropic, Google, DeepSeek).
- `llm_quest_benchmark/executors/cli/`:
  Typer CLI (`llm-quest`) entrypoints.
- `llm_quest_benchmark/web/`:
  Flask UI for quest execution, benchmarking, and analysis.
- `llm_quest_benchmark/tests/`:
  Unit + integration tests.

## Required Runtime Setup
1. Initialize submodule:
   - `git submodule update --init --recursive`
2. Install Python deps:
   - `uv sync --extra dev`
3. Install Node deps:
   - Repo root: `npm install`
   - Submodule: `cd space-rangers-quest && npm install --legacy-peer-deps && npm run build`
4. Create env file:
   - `cp .env.template .env`
5. For Node 23+:
   - `export NODE_OPTIONS=--openssl-legacy-provider`

## Common Commands
- CLI help:
  - `uv run llm-quest --help`
- Run random quest smoke:
  - `NODE_OPTIONS=--openssl-legacy-provider uv run llm-quest run --quest quests/Boat.qm --model random_choice --timeout 20 --debug`
- Run benchmark matrix:
  - `uv run llm-quest benchmark --config configs/test/test_benchmark.yaml`
- Start Flask UI:
  - `uv run llm-quest server`
- Run doc-gardening scan:
  - `./scripts/doc_gardening.sh audit . markdown`

## Doc-Gardening Trigger
- Mention `/doc-gardening` to trigger the `doc-gardening` skill workflow.
- Global skill source: `~/.codex/skills/doc-gardening/SKILL.md`.

## Documentation Index
- `README.md`: quickstart + usage.
- `docs/ARCHITECTURE.md`: system design and module responsibilities.
- `docs/API.md`: Flask web endpoints used by the UI.
- `docs/DEPLOYMENT.md`: non-local Flask deployment options (stable domain).
- `docs/RUNBOOK.md`: operations and troubleshooting.
- `docs/PLANS.md`: roadmap and execution plans.
- `docs/experiments/`: experiment logs and iteration notes.
