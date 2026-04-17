# LLM Quest Benchmark
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Benchmark for evaluating LLM agent architectures on interactive fiction quests. Measures how planning, tool use, and prompt design affect decision-making quality across models and tasks.

## What it does

- Runs LLM agents through choice-based text quests (Space Rangers .qm format, 150 quests, RU/EN)
- Compares agent modes: baseline, prompted reasoning, planner, tool-augmented
- Tracks success rate, token cost, repetition rate, and decision quality per run
- Supports OpenAI, Anthropic, Google Gemini, and DeepSeek providers
- YAML-driven benchmark configs for model/template/temperature matrix sweeps

## Setup

### Prerequisites
- Python 3.11+, Node.js 18+, `uv`

### Install

```bash
git clone --recursive https://github.com/yourconscience/llm_quest_benchmark.git
cd llm_quest_benchmark
uv sync --extra dev
npm install

cp .env.template .env
# Add your API keys: OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, DEEPSEEK_API_KEY

./download_quests.sh --refresh
```

## Usage

```bash
# Run one quest
llm-quest run --quest quests/Boat.qm --model gemini-2.5-flash --timeout 120

# Run benchmark matrix
llm-quest benchmark --config configs/benchmarks/mode_comparison_pilot.yaml

# Generate report from benchmark results
llm-quest benchmark-report --benchmark-id <id> --output report.md

# Analyze a single run
llm-quest analyze-run --run-summary results/<agent>/<quest>/run_<id>/run_summary.json

# Play as human in terminal
llm-quest play --quest quests/Boat.qm
```

## Project Structure

- `llm_quest_benchmark/agents/` - Agent implementations (LLM, planner, tool-augmented)
- `llm_quest_benchmark/prompt_templates/` - Jinja2 prompt templates per agent mode
- `llm_quest_benchmark/executors/` - CLI, benchmark orchestration, TS bridge
- `configs/benchmarks/` - YAML benchmark configurations
- `quests/` - Quest files (downloaded via `download_quests.sh`)
- `space-rangers-quest/` - TypeScript quest engine (submodule)
- `docs/` - Architecture and competitive landscape

## License
MIT
