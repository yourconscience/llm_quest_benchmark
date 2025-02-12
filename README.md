# LLM Quest Benchmark
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A framework for evaluating LLM performance on complex decision-making tasks using Space Rangers text quests. The project provides:

- **Quest Environment**: Run classic Space Rangers quests through a modern LLM-powered agent
- **Interactive Mode**: Play quests manually or let an LLM agent navigate them
- **Metrics Collection**: Track success rates, decision patterns, and performance metrics
- **Developer Tools**: Rich debugging, state history, and comprehensive testing

Built with LiteLLM for model access, Space Rangers Quest engine for parsing, and Rich for beautiful terminal output.

## Features

- Run quests with different LLM models (Claude, GPT-4, etc.)
- Interactive play mode with:
  - Auto-skip for simple choices
  - Rich terminal UI
  - Debug state inspection
  - State history tracking
- Comprehensive metrics collection
- Robust error handling and debugging
- Beautiful terminal UI with Rich

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

# Debug mode with state history
llm-quest play -q quests/boat.qm --debug
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
llm-quest run --log-level debug

# State inspection
llm-quest play --debug

# Timeout protection
llm-quest run --timeout 5
```

## CLI Options

### Common Options
- `--quest`: Quest file path (default: quests/boat.qm)
- `--log-level`: Logging level (debug, info, warning)
- `--metrics`: Enable metrics collection

### Run Mode Options
- `--model`: LLM model (sonnet, claude, gpt4)
- `--timeout`: Timeout in seconds (default: 60)

### Play Mode Options
- `--skip`: Auto-select single choices
- `--debug`: Show state history and debug info
- `--lang`: Quest language (rus, eng)

## Project Structure

- `llm_quest_benchmark/` - Core package
  - `core/` - Core functionality
  - `agents/` - LLM agents
  - `environments/` - Quest environments
  - `executors/` - CLI and bridges
    - `ts_bridge/` - Space Rangers Quest interface
  - `renderers/` - Terminal UI
  - `tests/` - Test suite
- `quests/` - Example quests
- `docs/` - Documentation

See [docs/roadmap.md](docs/roadmap.md) for development status and plans.

## Architecture

The project uses a simplified architecture with clear boundaries:
1. TypeScript bridge provides raw access to Space Rangers Quest engine
2. Python bridge handles state management and formatting
3. Environment provides clean interface for agents
4. Rich UI for beautiful terminal output

See [docs/qm_simplified_workflow.md](docs/qm_simplified_workflow.md) for details.

## License
MIT License - See LICENSE for details.

Disclaimer: This project is not affiliated with Elemental Games or the Space Rangers franchise.
