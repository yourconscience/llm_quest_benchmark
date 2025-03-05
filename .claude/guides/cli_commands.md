# CLI Commands Guide

## Core Commands

### Running Quests

```bash
# Run a quest with a specific LLM agent
llm-quest run --quest quests/Boat.qm --model gpt-4o --debug

# Run with a specific agent configuration
llm-quest run --quest quests/Boat.qm --agent calculator-agent --debug

# Play interactively as a human player
llm-quest play --quest quests/boat.qm --skip
```

### Benchmarking

```bash
# Run a benchmark with a configuration file
llm-quest benchmark --config configs/test_benchmark.yaml

# Run a partial benchmark with a subset of quests
llm-quest benchmark --config configs/test_benchmark.yaml --quests Boat.qm,Casino.qm
```

### Analysis

```bash
# Analyze the most recent run
llm-quest analyze --last

# Analyze a specific quest
llm-quest analyze --quest Boat.qm

# Analyze a benchmark
llm-quest analyze --benchmark first

# Export analysis to JSON
llm-quest analyze --last --export output.json

# Generate metrics report
llm-quest metrics report
```

### Web Interface

```bash
# Start the web server
llm-quest server

# Run in debug mode
llm-quest server --debug

# Run in production with workers
llm-quest server --production --workers 4
```

## Agent Management

```bash
# List available agents
llm-quest agents list

# Show agent details
llm-quest agents show calculator-agent

# Create a new agent
llm-quest agents new --yaml config.yaml

# Edit an existing agent
llm-quest agents edit memory-agent

# Delete an agent
llm-quest agents delete unused-agent

# Set memory configuration
llm-quest agents set-memory calculator-agent summary 15

# Add a tool to an agent
llm-quest agents add-tool memory-agent calculator

# Remove a tool from an agent
llm-quest agents remove-tool memory-agent calculator
```

## Development Commands

```bash
# Install dependencies
uv pip install -e .

# Run tests
pytest llm_quest_benchmark/tests/

# Run type checking
mypy llm_quest_benchmark

# Format code with pre-commit
pre-commit run --all-files
```
