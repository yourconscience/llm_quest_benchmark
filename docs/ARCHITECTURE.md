# Architecture

## Overview

LLM Quest Benchmark evaluates how **agent harnesses** complete interactive
fiction quests in the Space Rangers `.qm` format. The benchmark holds the quest
environment and result logging constant while varying the harness around the
model: prompt template, memory strategy, tools, and action loop.

The runtime loop is:

1. Parse or step quest state via the TypeScript engine bridge.
2. Build harness context from current state, available choices, and memory.
3. Get a choice from a human, random policy, or LLM-backed harness.
4. Apply the choice, log the step, and detect the terminal outcome.
5. Persist run metrics and run summaries.

## Main Runtime Layers

### 1. Quest Engine Layer

- `space-rangers-quest/`: TypeScript quest parser/player submodule.
- `llm_quest_benchmark/executors/ts_bridge/consoleplayer.ts`: Node entrypoint
  for parse/step execution.
- `llm_quest_benchmark/executors/ts_bridge/bridge.py`: Python subprocess
  bridge with startup preflight and actionable errors.

### 2. Environment Layer

- `llm_quest_benchmark/environments/qm.py`: Wraps the bridge into Python
  environment semantics (`reset`, `step`, terminal detection).

### 3. Harness Layer

- `llm_quest_benchmark/harnesses/base.py`: `BaseHarness`, the shared
  LLM-backed `QuestPlayer` implementation for prompt rendering, response
  parsing, retries, contextual state, and safety filtering.
- `llm_quest_benchmark/harnesses/memory.py`: `DefaultMemory`,
  `FullTranscriptMemory`, and `CompactionMemory`.
- `llm_quest_benchmark/harnesses/tools.py`: Calculator, scratchpad, and quest
  history helpers used by tool harnesses.
- `llm_quest_benchmark/harnesses/factory.py`: `create_harness()` and the
  canonical harness registry.
- `llm_quest_benchmark/agents/human_player.py`,
  `llm_quest_benchmark/agents/random_agent.py`: Non-LLM `QuestPlayer`
  implementations preserved for interactive and random baselines.

Harness construction lazily initializes provider clients, so template rendering
and benchmark configuration parsing do not require API keys.

### 4. LLM Provider Layer

- `llm_quest_benchmark/llm/client.py`:
  - provider/model normalization (`provider:model` + aliases)
  - adapters: OpenAI, Anthropic, Google Gemini, DeepSeek
  - shared retry/backoff and timeout handling
  - token/cost usage tracking per completion call

### 5. Execution and Analysis Layer

- `llm_quest_benchmark/core/runner.py`: Core quest run loop.
- `llm_quest_benchmark/core/analyzer.py`: Post-run analysis and benchmark
  summaries.
- `llm_quest_benchmark/core/benchmark_report.py`: Markdown report generator.
- `llm_quest_benchmark/core/logging.py`: Quest logger with per-run metrics
  (`repetition_rate`, `bad_decision_rate`).
- `llm_quest_benchmark/executors/benchmark.py`: Benchmark orchestration with
  parallel workers.
- `llm_quest_benchmark/executors/cli/commands.py`: CLI commands (`run`, `play`,
  `analyze`, `analyze-run`, `benchmark`, `benchmark-report`,
  `download-quests`, `cleanup`).

### 6. Prompt Templates

- `llm_quest_benchmark/prompt_templates/`: Jinja2 templates referenced by
  harnesses.
  - `stub.jinja`: Minimal prompt.
  - `reasoning.jinja`: Short-context or full-history reasoning depending on
    harness memory.
  - `stateful_compact.jinja`: Compact memory / 20-word memo prompt.
  - `stateful_compact_hints.jinja`: Compact memo prompt with mechanics hints.
  - `planner.jinja`: Planner loop prompt.
  - `tool_augmented.jinja`, `tool_augmented_hints.jinja`: Tool prompts with
    compact memory, optionally with hints.

## Persistence

- `metrics.db`: Benchmark/run metrics for CLI workflows.
- `results/<harness>/<quest>/run_<id>/run_summary.json`: Step trace,
  per-step decisions, and aggregated token/cost usage.

## Configuration

- `.env` (copied from `.env.template`): Provider API keys.
- `configs/benchmarks/`: Benchmark YAML configs defining model × harness ×
  quest matrices.

## Public Taxonomy (Benchmark Dimension)

| Public label | Harness name | Template | Memory | Tools | Loop |
|---|---|---|---|---|---|
| Minimal prompt | `minimal` | `stub.jinja` | `DefaultMemory` | none | react |
| Short-context reasoning | `reasoning_recent` | `reasoning.jinja` | `DefaultMemory` | none | react |
| Full-history reasoning | `reasoning_full` | `reasoning.jinja` | `FullTranscriptMemory` | none | react |
| Compact memory / memo | `memo_compact` | `stateful_compact.jinja` | `CompactionMemory` | none | react |
| Prompt hints | `hinted_compact` | `stateful_compact_hints.jinja` | `CompactionMemory` | none | react |
| Tools + compact memory | `tool_compact` | `tool_augmented.jinja` | `CompactionMemory` | calculator, scratchpad, quest history | tool-select-then-act |
| Tools + hints + compact memory | `tool_hinted` | `tool_augmented_hints.jinja` | `CompactionMemory` | calculator, scratchpad, quest history | tool-select-then-act |
| Planner loop | `planner` | `planner.jinja` | `CompactionMemory` | none | plan-maintain-act |
