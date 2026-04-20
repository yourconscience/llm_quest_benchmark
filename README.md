# LLM Quest Benchmark
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Leaderboard](https://img.shields.io/badge/Leaderboard-Live-green.svg)](https://yourconscience.github.io/llm_quest_benchmark/)
[![Paper](https://img.shields.io/badge/Paper-Draft-orange.svg)](https://yourconscience.github.io/llm_quest_benchmark/paper.html)

Benchmark for evaluating LLM agent architectures on interactive fiction quests. Measures how planning, tool use, and prompt design affect decision-making quality across models and tasks.

**[Project Site](https://yourconscience.github.io/llm_quest_benchmark/)** | **[Leaderboard](https://yourconscience.github.io/llm_quest_benchmark/index.html)** | **[Paper (draft)](https://yourconscience.github.io/llm_quest_benchmark/paper.html)**

```
================================================================================
Step 2
================================================================================
Agent's Thoughts:
{"analysis":"need to find escorts","reasoning":"spaceport is the logical place","result":1}
----------------------------------------
You leave the ship, squinting your eyes from the bright light of the star
Procyon. You look around for the attendants. There's nobody on the airfield.

Status:
Your money: 2000 cr.
You are absolutely calm.

Choices:
1. Wander over to the spaceport to look for your escorts.
2. Chat with the bartender.
```

## What it does

- Runs LLM agents through choice-based text quests (Space Rangers .qm format, 150 quests, RU/EN)
- Compares 5 agent architectures: baseline, prompted reasoning, knowledge-augmented, planner, tool-augmented
- Tracks success rate, exploration rate, repetition rate, and per-run token cost
- Benchmarks 6 mid-tier production models at comparable price points ($0.01-0.04/run): DeepSeek V3.2, Qwen3.5 Plus, Kimi K2.5, Gemini 3 Flash, GLM-5, GPT-5.4 Mini
- YAML-driven benchmark configs for model/mode/temperature matrix sweeps

## Quick Start (Docker)

```bash
git clone --recursive https://github.com/yourconscience/llm_quest_benchmark.git
cd llm_quest_benchmark

cp .env.template .env
# Add your API keys: OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, DEEPSEEK_API_KEY

# Run a single quest
docker compose run llm-quest run --quest quests/Boat.qm --model gemini-3-flash-preview

# Run a benchmark matrix
docker compose run llm-quest benchmark --config configs/benchmarks/mode_comparison_pilot.yaml
```

## Local Development

### Prerequisites
- Python 3.11+, Node.js 18+, `uv`

### Install

```bash
git clone --recursive https://github.com/yourconscience/llm_quest_benchmark.git
cd llm_quest_benchmark
uv sync --extra dev
npm install

cp .env.template .env
# Add your API keys

./download_quests.sh --refresh
```

### Usage

```bash
# Run one quest
llm-quest run --quest quests/Boat.qm --model gemini-3-flash-preview --timeout 120

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
- `docs/` - Dataset documentation (DATASHEET.md)
- `research/` - Error analysis, landscape comparison, paper planning (gitignored)

## License
MIT
