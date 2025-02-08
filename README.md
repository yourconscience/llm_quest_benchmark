# LLM Quest Benchmark
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Benchmark for testing LLM performance on Space Rangers text quests.

## Prerequisites

- Python 3.10+
- Node.js 18+ (for QM parser)
- Git (for submodules)

## Installation

1. Clone repository with submodules:
```bash
git clone https://github.com/yourconscience/llm-quest-benchmark --recurse-submodules
cd llm-quest-benchmark
```

2. Create and activate virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/MacOS
# or
.venv\Scripts\activate  # Windows
```

3. Install in development mode:
```bash
pip install -e .
npm install --prefix space-rangers-quest --legacy-peer-deps
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys
```

## Entry points

1. Run quest with live rendering:

```bash
llm-quest --quest quests/boat.qm --log-level debug
```
For headless operation:
```bash
llm-quest --log-level warning --output metrics.json > /dev/null
```

2. Analyze metrics:
```bash
llm-analyze metrics.json
```

Key options:
- `--quest`: Path to QM quest file (default: quests/boat.qm)
- `--log-level`: Set logging verbosity (debug, info, warning)
- `--output`: Save run metrics to JSON file


## Current Status [WIP]:
- [x] Simple parser for QM files
- [x] Basic state management and environment simulator
- [x] LLM-agents with OpenRouter support
- [x] Wrapper for roginvs/space-rangers-quest QM player + example quest
- [ ] QM parsing works for all needed quests
- [ ] Create prompt template based on game state and previous actions
- [ ] Add reward score for single run
- [ ] Prepare benchmark with multiple runs across different QM text quests


## Features
- **LiteLLM backend**: Supports multiple LLM providers through LiteLLM with built-in caching and routing.
- **OpenRouter Integration**: All latest cloud models are supported through OpenRouter.
- **Data contamination**: Original text data is translated/rephrased without semantic changes, ensuring it was not seen during training.
- **Complex decision making**: Benchmark focuses on LLM's ability to understand context and make consistent decisions in complex narrative environments.


## Project Structure

- `llm_quest_benchmark/` - Core package
  - `agents/` - Agent implementations
    - `llm_agent.py` - LLM-powered quest agent
  - `parsers/` - File parsers
    - `qm/` - QM file parsing
  - `renderers/` - Output renderers
  - `prompt_templates/` - Jinja templates
  - `scripts/` - CLI entry points
  - `tests/` - Test suite
- `quests/` - Example QM files
- `space-rangers-quest/` - TypeScript console player for Space Rangers quests
- `docs/` - Documentation and roadmap


## License
MIT License - See LICENSE for details.

Disclaimer: This project is not affiliated with Elemental Games or the Space Rangers franchise. Quest content is modified for research purposes only.
