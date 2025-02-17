# LLM Quest Benchmark
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Observe and analyze LLM agents decision-making through Space Rangers text adventures! 👾🚀📊

## Features

- 👾 **Quest Environment**: Classic Space Rangers text quests act as single-agent environments
- 🤖 **LLM Agents**: Simple yet customizable via prompt templates and optional thinking
- ⭐️ **Latest LLM Providers**: OpenAI, Anthropic, Deepseek, OpenRouter models are supported
- 🎮 **Interactive Mode**: Play quests as Human Agent in Rich terminal UI
- 📊 **Metrics Collection**: Track success rates, decision patterns, and performance metrics
- 🛠️ **Developer Tools**: Rich debugging, state history, and comprehensive testing

## Prerequisites

- Python 3.10+
- Node.js 18+ (for QM parser)
- Git (for submodules)

## Quick Start

1. Clone and setup:
```bash
git clone https://github.com/yourconscience/llm-quest-benchmark --recurse-submodules
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env  # Configure your API keys
```

2. Run a quest:
```bash
# Run with LLM agent
llm-quest run -q quests/boat.qm --model sonnet

# Play interactively
llm-quest play -q quests/boat.qm --skip

# Analyze quest run
llm-quest analyze  # Uses most recent run
llm-quest analyze --metrics-file metrics/quest_run_20250217_144717.jsonl
```

## Development

1. Install dev tools:
```bash
pip install -e ".[dev]"
pre-commit install
```

2. Run tests:
```bash
pytest                 # All tests
pytest -m integration  # Integration tests
pytest -m unit        # Unit tests
```

3. Debug options:
```bash
# Debug logging
llm-quest run --debug

# State inspection
llm-quest play --debug

# Analyze with debug info
llm-quest analyze --debug
```

## Project Structure

- `llm_quest_benchmark/` - Core package
  - `core/` - Core functionality (logging, runner)
  - `agents/` - LLM and human agents
  - `environments/` - Quest environments
  - `executors/` - CLI and bridges
  - `renderers/` - Terminal UI
  - `utils/` - Shared utilities
  - `tests/` - Test suite
- `quests/` - Example quests
- `docs/` - Documentation

See [docs/design.md](docs/design.md) for more details on the project design.

## License
MIT License - See LICENSE for details.

Disclaimer: This project is not affiliated with Elemental Games or the Space Rangers franchise.
