# LLM Quest Benchmark
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Leaderboard](https://img.shields.io/badge/Leaderboard-Live-green.svg)](https://yourconscience.github.io/llm_quest_benchmark/)
[![About](https://img.shields.io/badge/About-Post-blue.svg)](https://yourconscience.github.io/llm_quest_benchmark/about.html)

Benchmark for evaluating LLM context scaffolds on interactive fiction quests. Measures how prompt context, compact memory, tools, and planning loops affect sequential decision-making across models and tasks.

**[Project Site](https://yourconscience.github.io/llm_quest_benchmark/)** | **[Leaderboard](https://yourconscience.github.io/llm_quest_benchmark/index.html)** | **[About / Write-up](https://yourconscience.github.io/llm_quest_benchmark/about.html)**

See the [About page](https://yourconscience.github.io/llm_quest_benchmark/about.html) for the project narrative, taxonomy, metrics, caveats, and model selection rationale.

## Quick Start (Docker)

```bash
git clone --recursive https://github.com/yourconscience/llm_quest_benchmark.git
cd llm_quest_benchmark

cp .env.template .env
# Add your API keys in .env file

# Run a single quest
docker compose run llm-quest run --quest quests/Boat.qm --model gemini-3-flash-preview

# Run a benchmark matrix
docker compose run llm-quest benchmark --config configs/benchmarks/memory_full_transcript.yaml
```

## Local Development

### Prerequisites
- Python 3.11+, Node.js 18+, `uv`, `pnpm`

### Install

```bash
git clone --recursive https://github.com/yourconscience/llm_quest_benchmark.git
cd llm_quest_benchmark
uv sync --extra dev
pnpm install

cp .env.template .env
# Add your API keys

./download_quests.sh --refresh
```

### Usage

```bash
# Run one quest
uv run llm-quest run --quest quests/Boat.qm --model gemini-3-flash-preview --timeout 120

# Run benchmark matrix
uv run llm-quest benchmark --config configs/benchmarks/memory_full_transcript.yaml

# Generate report from benchmark results
uv run llm-quest benchmark-report --benchmark-id <id> --output report.md

# Analyze a single run
uv run llm-quest analyze-run --run-summary results/<agent>/<quest>/run_<id>/run_summary.json

# Play as human in terminal
uv run llm-quest play --quest quests/Boat.qm

# Build static site JS assets
pnpm run build

# Rebuild compressed Play quest assets after refreshing local quest files
pnpm run build:play-assets
```

## API Configuration

Set provider API keys in `.env` (see `.env.template`).

### OpenRouter

Any model on OpenRouter can be used with the `openrouter:` prefix:
```bash
uv run llm-quest run --model openrouter:openai/gpt-5.4-mini --quest quests/Boat.qm
```
Requires `OPENROUTER_API_KEY` in `.env`.

### OpenAI-compatible proxies (OAuth, local LLMs)

Set `OPENAI_BASE_URL` in `.env` to route the `openai:` provider through any compatible endpoint:
```bash
# .env - local OAuth proxy (CLIProxyAPI, codex-proxy, openai-oauth, etc.)
OPENAI_BASE_URL=http://localhost:8318/v1
```
No `OPENAI_API_KEY` needed when using a local proxy:
```bash
uv run llm-quest run --model gpt-5-mini --quest quests/Boat.qm
```
When `OPENAI_BASE_URL` is set, the client will not forward `OPENAI_API_KEY` to that endpoint.
If your proxy requires bearer auth, set `OPENAI_BASE_URL_API_KEY` explicitly.

### Direct API keys

Provider-specific keys in `.env`:
- `OPENAI_API_KEY` - OpenAI API
- `GOOGLE_API_KEY` / `GEMINI_API_KEY` - Google AI Studio
- `ANTHROPIC_API_KEY` - Anthropic API
- `DEEPSEEK_API_KEY` - DeepSeek API
- `OPENROUTER_API_KEY` - OpenRouter (multi-provider gateway)

## Project Structure

- `llm_quest_benchmark/harnesses/` - LLM harness implementations for prompt, memory, tools, and planning experiments
- `llm_quest_benchmark/agents/` - Non-LLM player primitives (`human`, `random_choice`)
- `llm_quest_benchmark/prompt_templates/` - Jinja2 prompt templates for the public context-scaffold taxonomy
- `llm_quest_benchmark/executors/` - CLI, benchmark orchestration, TS bridge
- `configs/benchmarks/` - YAML benchmark configurations
- `quests/` - Quest files (downloaded via `download_quests.sh`)
- `space-rangers-quest/` - TypeScript quest engine (submodule)
- `docs/ARCHITECTURE.md` - Runtime architecture and taxonomy mapping
- `docs/DATASHEET.md` - Dataset and public leaderboard slice documentation
- `research/` - Error analysis, landscape comparison (gitignored)

## Validation

```bash
uv run llm-quest --help
uv run ruff check .
uv run ruff format --check .
uv run pytest
pnpm run build
python3 -m json.tool site/leaderboard.json >/tmp/llm_quest_leaderboard_check.json

# Report-only for now: broad pre-existing typing backlog is not a release gate.
uv run mypy llm_quest_benchmark
```

## License
MIT
