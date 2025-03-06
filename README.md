# LLM Quest Benchmark
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Observe and analyze LLM agents decision-making through Space Rangers text adventures! 👾🚀📊

## Features

- 🔥 **Modern Web UI**: Check out the demo [here](https://cf82-94-43-167-97.ngrok-free.app)
- 👾 **Quest Environment**: Classic Space Rangers text quests act as single-agent environments
- 🤖 **LLM Agents**: Simple yet customizable via prompt templates and optional thinking
- 🧠 **Memory Systems**: Support for message history and summarization to improve agent performance
- 🧮 **Tool Support**: Calculator tool integration for agents to perform mathematical operations
- ⭐️ **Latest LLM Providers**: OpenAI, Anthropic, Deepseek, OpenRouter models are supported
- 🎮 **Interactive Mode**: Play quests as Human Agent in Rich terminal UI
- 📊 **Metrics Collection**: Track success rates, decision patterns, memory usage, and tool performance

## Setup

### Prerequisites
- Python 3.11 or higher
- Node.js 18 or higher (Note: For Node.js 23+ you'll need to set `NODE_OPTIONS=--openssl-legacy-provider`)
- npm 9 or higher

### Installation

1. Clone the repository with submodules:
```bash
git clone --recursive https://github.com/your-username/llm_quest_benchmark.git
cd llm_quest_benchmark
```

2. Run the installation script:
```bash
# On Linux/macOS
chmod +x install.sh
./install.sh

# On Windows
.\install.ps1
```

The script will:
- Install uv (modern Python package manager)
- Set up a virtual environment
- Install Python dependencies
- Set up the Space Rangers Quest TypeScript bridge
- Create a default .env file

4. Configure your API keys in .env file or set it in the environment:
```bash
export OPENAI_API_KEY=your-api-key  # On Windows: set OPENAI_API_KEY=your-api-key
```

5. Download quests from [gitlab](https://gitlab.com/spacerangers/spacerangers.gitlab.io/-/tree/master/borrowed/qm)

## Usage

### CLI Interface
```bash
# Run with LLM agent
llm-quest run -q quests/boat.qm --model gpt-4o-mini

# Play interactively
llm-quest play -q quests/boat.qm --skip

# Analyze quest run
llm-quest analyze  # Uses most recent run

# Run benchmark
llm-quest benchmark --config configs/test_benchmark.yaml

# List available agents
llm-quest agents list

# Show agent details
llm-quest agents show calculator-agent

# Create a new agent
llm-quest agents new [--yaml config.yaml]

# Configure agent memory
llm-quest agents set-memory calculator-agent summary 15

# Add calculator tool to agent
llm-quest agents add-tool memory-agent calculator

# Generate metrics report
llm-quest metrics report
```

### Web Interface
```bash
# Start the web server
llm-quest server

# For debug mode
llm-quest server --debug
```

Then open http://localhost:8000 in your browser.

## Project Structure

- `llm_quest_benchmark/` - Core package
  - `core/` - Core functionality (logging, runner)
  - `agents/` - LLM and human agents
  - `environments/` - Quest environments
  - `executors/` - CLI and bridges
  - `renderers/` - Terminal UI
  - `web/` - Web interface
  - `utils/` - Shared utilities
  - `tests/` - Test suite
- `quests/` - Example quests
- `agents/` - Agent configuration files

## Memory and Tool System

### Memory Types
- **Message History**: Maintains a history of recent steps (default max: 10)
- **Summary**: Uses LLM to create concise summaries of past interactions

### Tools
- **Calculator**: Allows agents to perform mathematical operations

## Development

### Setting Up Pre-Commit Hooks

Run these commands to set up the pre-commit hooks for code formatting:

```bash
# Install pre-commit and hooks
uv pip install pre-commit
pre-commit install

# Run hooks manually on all files
pre-commit run --all-files
```

The pre-commit setup includes:
- yapf for Python code formatting
- isort for import sorting
- Various file checks (YAML validation, whitespace trimming, etc.)

### Running Tests

```bash
# Run all tests
pytest

# Run specific tests
pytest llm_quest_benchmark/tests/path/to/test.py::TestClass::test_method
```

## License
MIT License - See LICENSE for details.

## Disclaimer
This project was created for fun with 99% code written by cursor's AI agent mode.

This project is not affiliated with Elemental Games or the Space Rangers franchise.
