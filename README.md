# LLM Quest Benchmark
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Observe and analyze LLM agents decision-making through Space Rangers text adventures! 👾🚀📊

## Features

- 🔥 **Modern Web UI**: Check out the demo: https://9b8c-94-43-167-97.ngrok-free.app
- 👾 **Quest Environment**: Classic Space Rangers text quests act as single-agent environments
- 🤖 **LLM Agents**: Simple yet customizable via prompt templates and optional thinking
- ⭐️ **Latest LLM Providers**: OpenAI, Anthropic, Deepseek, OpenRouter models are supported
- 🎮 **Interactive Mode**: Play quests as Human Agent in Rich terminal UI
- 📊 **Metrics Collection**: Track success rates, decision patterns, and performance metrics

## Setup

### Prerequisites
- Python 3.11 or higher
- Node.js 18 or higher (Note: For Node.js 23+ you'll need to set `NODE_OPTIONS=--openssl-legacy-provider`)
- npm 9 or higher
- uv (modern Python package manager)

### Installation

1. Install uv:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Clone the repository with submodules:
```bash
git clone --recursive https://github.com/your-username/llm_quest_benchmark.git
cd llm_quest_benchmark
```

3. Run the installation script:
```bash
chmod +x install.sh
./install.sh
```

The script will:
- Set up a virtual environment using uv
- Install Python dependencies using uv
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
```

### Web Interface
```bash
# Start the web server
llm-quest server
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

## License
MIT License - See LICENSE for details.

## Disclaimer
This project was created for fun with 99% code written by cursor's AI agent mode.

This project is not affiliated with Elemental Games or the Space Rangers franchise.
