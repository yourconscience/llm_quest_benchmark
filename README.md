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
```bash:setup.py
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

1. Run quest with live rendering:

```bash
llm-quest run --quest quests/boat.qm --log-level debug
```
For headless operation:
```bash
llm-quest run --quest quests/boat.qm --log-level warning --output metrics.json > /dev/null
```

2. Analyze metrics:
```bash
llm-quest analyze --metrics-file metrics.json
```

3. Run interactive quest player:
```bash
llm-quest play --quest quests/boat.qm
```

Key options:
- `--quest`: Path to QM quest file (default: quests/boat.qm)
- `--log-level`: Set logging verbosity (debug, info, warning)
- `--output`: Save run metrics to JSON file
- `--model`: LLM model to use (openai, anthropic, deepseek)


## Current Status [✅ Basic Player Implemented]:
- [x] Basic state management and environment simulator
- [x] LLM-agents with OpenRouter support
- [x] Wrapper for roginvs/space-rangers-quest QM player + example quest
- [x] QM parsing works for all needed quests
- [x] Interactive console player with rich terminal output


```
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


## Appendix

### Node.js & TypeScript Setup for the space-rangers-quest Submodule

After you clone the repository with submodules, perform the following steps to ensure the TypeScript code can compile correctly:

1. **Install dependencies:**
   ```bash
   cd space-rangers-quest
   npm install --legacy-peer-deps
   npm install --save-dev @types/node
   ```

2. **(Optional) Build the TypeScript code:**
   ```bash
   npm run build
   ```

### Metrics Collection

Enable automatic metrics logging with the `--metrics` flag:

```bash
# For automated runs
llm-quest run --quest quests/boat.qm --metrics

# For interactive play
llm-quest play --quest quests/boat.qm --metrics
```

Metrics are saved to the `metrics/` directory with filenames like `boat_20240315_143022.json`.
