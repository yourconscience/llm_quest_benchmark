# LLM Quest Benchmark
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Advanced framework for evaluating LLM decision-making in complex narrative environments using Space Rangers QM quests.

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
- **Data contamination**: Original quests are contaminated with rephrased text / translations, ensuring that data was not exposed during training.
- **Complex decision making**: Benchmark focuses on LLM's ability to understand context and make consistent decisions in complex narrative environments.


## Setup

1. Clone the repository and install dependencies:
```bash
git clone https://github.com/yourconscience/llm-quest-benchmark
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

## Usage (WIP)

```python
benchmark = QuestBenchmark(
    qm_path="quests/example.qm",
    agents=["openrouter/deepseek/deepseek-chat",
            "openrouter/anthropic/claude-3-5-sonnet"]
)

results = []
for agent in benchmark.agents:
    episode_result = benchmark.run_episode(agent)
    results.append({
        "model": agent.model,
        **episode_result
    })
```

## License
MIT License - See LICENSE for details.

Disclaimer: This project is not affiliated with Elemental Games or the Space Rangers franchise. Quest content is modified for research purposes only.
