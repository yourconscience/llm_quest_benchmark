# LLM Quest Benchmark
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Observe and analyze LLM agents decision-making through Space Rangers text adventures! 👾🚀📊

## Features

- 🔥 **Flask Web UI**: Run quests from browser, inspect playthroughs, and view run analytics
- 👾 **Quest Environment**: Space Rangers text quests wrapped as agent-friendly environments via TS bridge
- 🤖 **LLM Agents**: OpenAI, Anthropic, Google Gemini, and DeepSeek models supported
- 🧠 **Prompt Templates**: Swap strategy/reasoning templates without changing runner code
- 🎮 **Interactive Mode**: Play quests as a human agent in terminal UI
- 📊 **Run Artifacts**: Compact `run_summary.json` logs per run for easy analysis/iteration
- 🧪 **Benchmark Mode**: YAML-driven experiment matrix for model/template/temperature sweeps
- 🔍 **CLI Diagnostics**: `analyze` for DB metrics + `analyze-run` for decision-by-decision trace debugging

## What's Updated

- ✅ Quest downloader now rebuilds a flat, normalized layout under `quests/` (no nested source tree needed)
- ✅ Run summaries now use a compact schema focused on observation/choices/LLM decision
- ✅ Added CLI run-summary analyzer for faster prompt/config iteration loops
- ✅ Existing Flask workflow remains primary web interface (no Vercel dependency)

## Setup

### Option 1: Using Docker

1. Clone the repository:
```bash
git clone --recursive https://github.com/yourconscience/llm_quest_benchmark.git
cd llm_quest_benchmark
```

2. Configure environment:
```bash
cp .env.template .env
# Edit .env with your provider API keys
```

3. Start services:
```bash
docker-compose up -d
```

4. Open the app at [http://localhost:8000](http://localhost:8000).

### Option 2: Manual Installation

#### Prerequisites
- Python 3.11+
- Node.js 18+
- npm 9+
- `uv` package manager

#### Installation

1. Clone repository with submodules:
```bash
git clone --recursive https://github.com/yourconscience/llm_quest_benchmark.git
cd llm_quest_benchmark
git submodule update --init --recursive
```

2. Install Python deps:
```bash
uv sync --extra dev
```

3. Install Node deps:
```bash
npm install
cd space-rangers-quest
npm install --legacy-peer-deps
npm run build
cd ..
```

4. Configure API keys:
```bash
cp .env.template .env
# Edit .env with OPENAI_API_KEY / ANTHROPIC_API_KEY / GOOGLE_API_KEY / DEEPSEEK_API_KEY
```

5. Download quests into normalized local layout:
```bash
./download_quests.sh --refresh
```

## Usage

### CLI Interface
```bash
# Run one quest with an LLM agent
uv run llm-quest run --quest quests/kr_1_ru/Diehard.qm --model gpt-5-mini --timeout 120 --debug

# Play as human in terminal
uv run llm-quest play --quest quests/kr_1_ru/Boat.qm --skip

# Run benchmark from YAML config
uv run llm-quest benchmark --config configs/benchmarks/provider_suite_v2.yaml

# Analyze DB metrics (latest run / quest / benchmark)
uv run llm-quest analyze --last

# Analyze one run_summary decision trace
uv run llm-quest analyze-run --agent llm_gpt-5-mini --quest Diehard
# or
uv run llm-quest analyze-run --run-summary results/llm_gpt-5-mini/Diehard/run_123/run_summary.json
```

### Web Interface
```bash
uv run llm-quest server
```
Then open [http://localhost:8000](http://localhost:8000).

## Quest Layout

`download_quests.sh` builds this normalized structure:

- `quests/kr_1_ru`
- `quests/sr_2_1_2121_eng`
- `quests/sr_2_1_2170_ru`
- `quests/sr_2_2_1_2369_ru`
- `quests/sr_2_dominators_ru`
- `quests/sr_2_revolution_ru`
- `quests/sr_2_revolution_fan_ru`
- `quests/sr_2_reboot_ru`
- `quests/fanmade_ru`

## Project Structure

- `llm_quest_benchmark/` - Core package
- `configs/` - Run and benchmark configurations
- `quests/` - Local normalized quest files
- `results/` - Run artifacts and summaries
- `space-rangers-quest/` - TypeScript quest engine submodule

## License
MIT License - See LICENSE for details.

## Disclaimer
This project was created for fun with heavy AI-assisted coding.

This project is not affiliated with Elemental Games or the Space Rangers franchise.
