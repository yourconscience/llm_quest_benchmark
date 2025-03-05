# Repository Structure Guide

## Core Directories

- `llm_quest_benchmark/`: Main package code
  - `agents/`: Agent implementations (LLM agents, human player, etc.)
  - `core/`: Core functionality (runner, analyzer, logging)
  - `environments/`: QM environment implementation
  - `executors/`: CLI and web server implementation
  - `llm/`: LLM client and prompt handling
  - `prompt_templates/`: Jinja templates for LLM prompts
  - `renderers/`: Output rendering (terminal, progress, benchmark results)
  - `schemas/`: Data model definitions
  - `tests/`: Unit and integration tests
  - `utils/`: Shared utilities
  - `web/`: Web interface implementation

- `agents/`: Agent configuration files (JSON)
- `configs/`: Benchmark configuration files (YAML)
- `quests/`: Quest files (.qm format)
- `space-rangers-quest/`: QM parser implementation (TypeScript)

## Key Files

- `llm_quest_benchmark/constants.py`: Global constants including tools and memory types
- `llm_quest_benchmark/schemas/agent.py`: Agent configuration schema
- `llm_quest_benchmark/llm/prompt.py`: Prompt rendering and memory/tool handling
- `llm_quest_benchmark/core/analyzer.py`: Metrics analysis and reporting

## Memory System

The memory system supports two types:
- `message_history`: Stores raw history of interactions
- `summary`: Uses LLMs to create a condensed summary of past interactions

## Tool System

Current tools:
- `calculator`: Simple calculator tool for mathematical operations

## How to Find Things

Use ripgrep (`rg`) for efficient searching:

```bash
# Find files by name
rg -l "filename_pattern"

# Search for code patterns
rg "search_pattern"

# Search in specific files
rg "pattern" --glob "*.py"

# Search in specific directories
rg "pattern" path/to/dir
```
