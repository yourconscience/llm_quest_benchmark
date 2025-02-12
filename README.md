# LLM Quest Benchmark
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A framework for evaluating LLM performance on complex decision-making tasks using Space Rangers text quests. The project provides:

- **Quest Environment**: Run classic Space Rangers quests through a modern LLM-powered agent
- **Interactive Mode**: Play quests manually or let an LLM agent navigate them
- **Metrics Collection**: Track success rates, decision patterns, and performance metrics
- **Developer Tools**: Rich debugging, timeout handling, and comprehensive testing

Built with LiteLLM for model access, TypeScript for quest parsing, and Rich for beautiful terminal output.

## Features

- Run quests with different LLM models (Claude, GPT-4, etc.)
- Interactive play mode with auto-skip for simple choices
- Debug logging and timeout protection
- Metrics collection and analysis
- Beautiful terminal UI with Rich
- Comprehensive test suite

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
llm-quest run -q quests/boat.qm --model sonnet  # Run with LLM
llm-quest play -q quests/boat.qm --skip         # Play interactively
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

3. Debug mode:
```bash
llm-quest run --log-level debug --timeout 5
```

## CLI Options

- `--quest`: Quest file path (default: quests/boat.qm)
- `--model`: LLM model (sonnet, claude, gpt4)
- `--log-level`: Logging level (debug, info, warning)
- `--timeout`: Timeout in seconds (default: 60)
- `--skip`: Auto-select single options
- `--metrics`: Enable metrics collection

## Project Structure

- `llm_quest_benchmark/` - Core package
  - `core/` - Core functionality
  - `agents/` - LLM agents
  - `environments/` - Quest environments
  - `executors/` - CLI and bridges
  - `tests/` - Test suite
- `quests/` - Example quests
- `docs/` - Documentation

See [docs/roadmap.md](docs/roadmap.md) for development status and plans.

## License
MIT License - See LICENSE for details.

Disclaimer: This project is not affiliated with Elemental Games or the Space Rangers franchise.
