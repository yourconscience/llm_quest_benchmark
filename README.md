# LLM Quest Benchmark
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Benchmark for testing LLM performance on Space Rangers text quests.

## Prerequisites

- Python 3.10+
- Node.js 18+ (for QM parser)
- Git (for submodules)

## Installation

1. Clone with submodules:
```bash
git clone https://github.com/yourconscience/llm-quest-benchmark --recurse-submodules
```

2. Set up Python environment:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

3. Install pre-commit hooks:
```bash
pre-commit install
```

4. Configure environment:
```bash
cp .env.example .env
```

## Entry points

1. Run quest with LLM agent:
```bash
llm-quest run --quest quests/boat.qm --log-level debug --model sonnet
```

2. Play quest interactively:
```bash
llm-quest play --quest quests/boat.qm --skip
```

3. Analyze metrics:
```bash
llm-quest analyze --metrics-file metrics/latest.json
```

Key options:
- `--quest`: Path to QM quest file (default: quests/boat.qm)
- `--log-level`: Set logging verbosity (debug, info, warning)
- `--model`: LLM model to use (sonnet, claude, gpt4)
- `--timeout`: Set timeout in seconds (default: 60)
- `--skip`: Auto-select single options in play mode
- `--metrics`: Enable metrics collection

## Current Status [✅ Core Features]:
- [x] Basic state management and environment simulator
- [x] LLM-agents with OpenRouter support
- [x] QM parser integration with TypeScript bridge
- [x] Interactive console player with rich output
- [x] Automated testing with timeouts
- [x] Metrics collection and analysis
- [ ] Stable QM parsing for all quests
- [ ] Improved prompt templates
- [ ] Multi-run benchmarking

## Features
- **LiteLLM backend**: Supports multiple LLM providers through LiteLLM with built-in caching and routing
- **OpenRouter Integration**: All latest cloud models supported through OpenRouter
- **Rich Debug Logging**: Comprehensive debug output for development and testing
- **Automated Testing**: Integration tests with timeouts and metrics collection
- **Interactive Mode**: Play quests manually or with auto-skip for single options

## Project Structure

- `llm_quest_benchmark/` - Core package
  - `core/` - Core functionality
    - `runner.py` - Quest execution
    - `utils.py` - Common utilities
  - `agents/` - Agent implementations
  - `environments/` - Quest environments
  - `executors/` - CLI and bridges
  - `renderers/` - Output renderers
  - `tests/` - Test suite
    - `integration/` - E2E tests
    - `core/` - Core tests
- `quests/` - Example QM files
- `space-rangers-quest/` - TypeScript QM parser

## Development

1. Run tests:
```bash
pytest
```

2. Run specific test category:
```bash
pytest -m integration  # Integration tests
pytest -m unit        # Unit tests
```

3. Debug mode:
```bash
llm-quest run --log-level debug --timeout 5  # Short timeout for testing
```

## License
MIT License - See LICENSE for details.

Disclaimer: This project is not affiliated with Elemental Games or the Space Rangers franchise.
