# Architecture

## Overview
LLM Quest Benchmark evaluates how different agent architectures complete interactive fiction quests (Space Rangers `.qm` format).
The runtime loop is:
1. Parse or step quest state via the TypeScript engine bridge.
2. Build an action prompt from current state and available choices.
3. Get agent choice (human/random/LLM with varying agent modes).
4. Apply choice, log step, and detect outcome.
5. Persist run metrics and run summaries.

## Main Runtime Layers

### 1. Quest Engine Layer
- `space-rangers-quest/`:
  TypeScript quest parser/player submodule.
- `llm_quest_benchmark/executors/ts_bridge/consoleplayer.ts`:
  Node entrypoint for parse/step execution.
- `llm_quest_benchmark/executors/ts_bridge/bridge.py`:
  Python subprocess bridge with startup preflight and actionable errors.

### 2. Environment Layer
- `llm_quest_benchmark/environments/qm.py`:
  Wraps bridge into Python environment semantics (`reset`, `step`, terminal detection).

### 3. Agent Layer
- `llm_quest_benchmark/agents/llm_agent.py`: Base LLM agent with template-driven prompts, retry logic, loop-breaking, and safety filters.
- `llm_quest_benchmark/agents/planner_agent.py`: Planner loop with observation-diff heuristic for re-planning.
- `llm_quest_benchmark/agents/tool_agent.py`: Tool-using scaffold with quest history tool.
- `llm_quest_benchmark/agents/agent_factory.py`: Factory that maps template aliases (stub, reasoning, planner, tool_augmented) to agent classes.
- `llm_quest_benchmark/agents/human_player.py`, `random_agent.py`: Non-LLM agents.

`LLMAgent` lazily initializes provider clients, so template rendering and agent construction do not require API keys.

### 4. LLM Provider Layer
- `llm_quest_benchmark/llm/client.py`:
  - provider/model normalization (`provider:model` + aliases)
  - adapters: OpenAI, Anthropic, Google Gemini, DeepSeek
  - shared retry/backoff and timeout handling
  - token/cost usage tracking per completion call

### 5. Execution and Analysis Layer
- `llm_quest_benchmark/core/runner.py`: Core quest run loop.
- `llm_quest_benchmark/core/analyzer.py`: Post-run analysis and benchmark summaries.
- `llm_quest_benchmark/core/benchmark_report.py`: Markdown report generator.
- `llm_quest_benchmark/core/logging.py`: Quest logger with per-run metrics (repetition_rate, bad_decision_rate).
- `llm_quest_benchmark/executors/benchmark.py`: Benchmark orchestration with parallel workers.
- `llm_quest_benchmark/executors/cli/commands.py`: CLI commands (`run`, `play`, `analyze`, `analyze-run`, `benchmark`, `benchmark-report`, `download-quests`, `cleanup`).

### 6. Prompt Templates
- `llm_quest_benchmark/prompt_templates/`: Jinja2 templates for each agent mode.
  - `stub.jinja`: Minimal prompt.
  - `reasoning.jinja`, `strategic.jinja`, etc.: Short-context or full-history reasoning depending on memory mode.
  - `stateful_compact.jinja`, `memo_*.jinja`: Compact memory / memo prompts.
  - `light_hints.jinja`, `stateful_compact_hints.jinja`: Prompt hints.
  - `planner.jinja`: Planner loop prompts.
  - `tool_augmented.jinja`, `tool_augmented_hints.jinja`: Tool prompts with compact memory, optionally with hints.

## Persistence
- `metrics.db`: Benchmark/run metrics for CLI workflows.
- `results/<agent>/<quest>/run_<id>/run_summary.json`: Step trace + per-step decisions + aggregated token/cost usage.

## Configuration
- `.env` (copied from `.env.template`): Provider API keys.
- `configs/benchmarks/`: Benchmark YAML configs defining model x template x quest matrix.

## Public Taxonomy (Benchmark Dimension)
| Label | Template / memory source | Agent Class | Description |
|------|----------|-------------|-------------|
| Minimal prompt | stub | LLMAgent | Smallest action-selection prompt |
| Short-context reasoning | reasoning/strategic + default memory | LLMAgent | Local prompted analysis |
| Full-history reasoning | reasoning + full transcript memory | LLMAgent | Whole transcript retained in context |
| Compact memory / memo | reasoning/stateful/memo templates + compaction | LLMAgent | Summarized state instead of unbounded transcript |
| Prompt hints | light_hints/stateful_compact_hints | LLMAgent | Mechanics hints injected into prompt |
| Tools + compact memory | tool_augmented | ToolAgent | Quest history/scratchpad tools with compact context |
| Tools + hints + compact memory | tool_augmented_hints | ToolAgent | Tool scaffold plus prompt hints |
| Planner loop | planner | PlannerAgent | Plan-maintain-act loop |
