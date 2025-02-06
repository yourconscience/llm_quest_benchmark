# LLM Quest Benchmark
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Benchmark for evaluating LLM decision-making in complex narrative environments using Space Rangers text quests.

## Overview
This benchmark uses text quests (.qm files) from the classic game "Space Rangers" as a testing ground for LLM agents.
Each quest represents a complex decision tree with:
- Multiple valid paths to success/failure with clear win/loss conditions
- Parameter-based state tracking
- Long-term consequences of decisions

The system evaluates LLMs on their ability to:
- Understand context and make consistent decisions
- Optimize for long-term outcomes


## Features
- **LiteLLM backend**: Supports multiple LLM providers through LiteLLM with built-in caching and routing.
- **OpenRouter Integration**: All latest cloud models are supported through OpenRouter.
- **Data contamination**: Original text data is translated/rephrased without semantic changes, ensuring it was not seen during training.
- **Complex decision making**: Benchmark focuses on LLM's ability to understand context and make consistent decisions in complex narrative environments.

## Current Status [WIP]:
- [x] Simple parser for QM files
- [x] Basic state management and environment simulator
- [x] LLM-agents with OpenRouter support
- [x] Wrapper for roginvs/space-rangers-quest QM player + example quest
- [ ] QM parsing works for all needed quests
- [ ] Create prompt template based on game state and previous actions
- [ ] Add reward score for single run
- [ ] Prepare benchmark with multiple runs across different QM text quests

## Setup
1. Clone the repository with submodules and install dependencies:
```bash
git clone https://github.com/yourconscience/llm-quest-benchmark --recurse-submodules
cd llm-quest-benchmark
pip install -r requirements.txt
```

2. Copy `.env.template` to `.env` and add your API keys:
```bash
cp .env.template .env
```

Supported providers:
- OpenAI (GPT models)
- Anthropic (Claude models)
- OpenRouter (various models)

Note: Local LLM support is not included in the initial version but can be added through LiteLLM customization.

## Usage example

```python
from src import qm_parser, llm_agent, simulator

MAX_ITER = 500

# Load quest data
with open("quests/boat.qm", "rb") as f:
    qm_data = qm_parser.parse_qm(f.read())

# Initialize components
agent = llm_agent.QuestAgent()
simulator = simulator.QuestSimulator(qm_data, agent)

# Run quest simulation
state = simulator.reset()
n_iter = 0
while n_iter < MAX_ITER:
    result = simulator.step()
    print(f"Day {state.days_passed}: {result.transition.description}")
    if result.done:
        print(f"Quest completed! Reward: {result.reward}")
        break
    n_iter += 1
```

## License
MIT License - See LICENSE for details.

Disclaimer: This project is not affiliated with Elemental Games or the Space Rangers franchise. Quest content is modified for research purposes only.
