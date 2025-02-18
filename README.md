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

## Setup

1. **Install Required Software**:
   - Python 3.9 or later from [Python.org](https://www.python.org/downloads/)
   - Node.js 18 or later from [nodejs.org](https://nodejs.org/)
   - Git (for cloning the repository)

2. **Get the Code**:
```bash
git clone https://github.com/yourconscience/llm-quest-benchmark --recurse-submodules
cd llm-quest-benchmark
```

3. **Setup Environment**:

On Unix/Mac/WSL:
```bash
./install.sh
source .venv/bin/activate
```

On Windows (PowerShell):
```powershell
# First time only: Allow script execution
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
# Then install
./install.ps1
```

4. **Configure API Keys**:
```bash
cp .env.example .env  # Then edit .env with your API keys
```

## Usage

```bash
# Run with LLM agent
llm-quest run -q quests/boat.qm --model gpt-4o-mini

# Play interactively
llm-quest play -q quests/boat.qm --skip

# Analyze quest run
llm-quest analyze  # Uses most recent run
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

## License
MIT License - See LICENSE for details.

Disclaimer: This project is not affiliated with Elemental Games or the Space Rangers franchise.
