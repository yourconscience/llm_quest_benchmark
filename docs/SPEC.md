# SPEC: LLM-Quest Current State

This document is a current-state project specification, not a roadmap promise.
For the public narrative and interpretation of results, use the project
[About page](../site/about.html) as the main story surface.

## Purpose

LLM Quest Benchmark evaluates how LLMs make sequential choices in Space
Rangers text quests. The benchmark varies the context scaffold around a model
while holding the quest environment and result logging consistent.

The core question is practical: which kinds of context help, hurt, or expose
state-tracking failures during 10-50 turn interactive fiction tasks?

## Current Public Scope

The public leaderboard is a curated comparable slice, not the full raw
experiment history. It currently reports:

- 6 primary publication models.
- 15 comparable quest IDs with coverage across all six primary models.
- 1,615 published leaderboard runs.
- Exploratory, one-model, and partial-coverage runs excluded from the public
  comparison slice unless they support direct comparison.

Raw benchmark artifacts and experiment notes remain useful for follow-up
analysis, but the public slice is the authoritative comparison surface.

## Current Taxonomy

Use these labels for current public descriptions of benchmark modes:

| Label | Implementation source | Agent class |
|---|---|---|
| Minimal prompt | `stub.jinja` | `LLMAgent` |
| Short-context reasoning | `reasoning.jinja`, `strategic.jinja` with default/recent context | `LLMAgent` |
| Full-history reasoning | reasoning templates with `full_transcript` memory | `LLMAgent` |
| Compact memory / memo | `stateful_compact.jinja`, memo templates, compaction memory | `LLMAgent` |
| Prompt hints | `light_hints.jinja`, `stateful_compact_hints.jinja` | `LLMAgent` |
| Tools + compact memory | `tool_augmented.jinja` | `ToolAgent` |
| Tools + hints + compact memory | `tool_augmented_hints.jinja` | `ToolAgent` |
| Planner loop | `planner.jinja` | `PlannerAgent` |

Older internal experiment labels are historical and should not be presented as
the current public taxonomy.

## Implemented Runtime

- Quest execution uses the TypeScript `space-rangers-quest` submodule through
  the Python bridge in `llm_quest_benchmark/executors/ts_bridge/`.
- Environment state is exposed through `llm_quest_benchmark/environments/qm.py`.
- Agents live under `llm_quest_benchmark/agents/` and are selected by template
  aliases and agent factory wiring.
- Provider calls are normalized in `llm_quest_benchmark/llm/client.py` with
  OpenAI-compatible, Anthropic, Google, and DeepSeek adapters.
- Benchmark execution is CLI + YAML driven through `uv run llm-quest ...`.
- Static public results are generated into `site/leaderboard.json` and rendered
  by `site/index.html`.

## Metrics

Current public metrics include success rate, average steps, token/cost
statistics, and repetition rate. Repetition is interpreted as a diagnostic
signal for loopiness or context loss, not as a solved predictor of success.

Progress-style metrics and richer quest difficulty annotations remain future
work unless present in generated result artifacts.

## Data and Distribution

Quest files are downloaded with `download_quests.sh` from the Space Rangers
community archive and are not redistributed as benchmark source data. The
repository includes benchmark code, configs, tests, static site assets, and the
curated public leaderboard JSON.

## Non-goals

- Claiming that any context scaffold is universally best. Results are jagged by
  quest and model.
- Treating exploratory or partial-coverage runs as public comparison data.
- Adding a production web service; the benchmark remains CLI/YAML first with a
  static publication site.
- Changing quest authoring or the upstream quest format.

## Reproducibility Entry Points

```bash
uv sync --extra dev
pnpm install
uv run llm-quest --help
uv run llm-quest benchmark --config configs/benchmarks/memory_full_transcript.yaml
pnpm run build
```

Provider API keys are required for real LLM runs. Tests and static validation
should run without external credentials in a prepared checkout.

Reproducible benchmark rows depend on recording the quest file, model/provider
ID, prompt templates, memory mode, run ID, outcome, and run summaries with
usage/metrics. Agent responses are parsed into a chosen action plus optional
analysis/reasoning so action validity, terminal outcome, steps, tokens/cost,
and repetition diagnostics can be regenerated from stored artifacts.
