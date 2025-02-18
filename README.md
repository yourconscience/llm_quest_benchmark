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
# On Unix/Mac:
chmod +x install.sh
./install.sh

# On Windows:
.\install.ps1
```

The script will:
- Install uv (modern Python package manager)
- Set up a virtual environment
- Install Python dependencies
- Set up the Space Rangers Quest TypeScript bridge
- Create a default .env file

3. Configure your API keys in .env file or set it in the environment:
```bash
export OPENAI_API_KEY=your-api-key  # On Windows: set OPENAI_API_KEY=your-api-key
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

### Troubleshooting

If you encounter issues with the Space Rangers Quest TypeScript bridge:

1. Make sure you have Node.js 18+ installed:
```bash
node --version
```

2. If using Node.js 23 or higher, set the OpenSSL legacy provider:
```bash
# Unix/Mac:
export NODE_OPTIONS=--openssl-legacy-provider

# Windows:
set NODE_OPTIONS=--openssl-legacy-provider
```

3. Clear npm cache and node_modules:
```bash
cd space-rangers-quest
rm -rf node_modules  # On Windows: rmdir /s /q node_modules
npm cache clean --force
npm install --legacy-peer-deps
```

4. If you see TypeScript/JSX errors, they can be safely ignored as they don't affect the bridge functionality.
