# SPEC: LLM-Quest Current State

This document is a current-state project specification, not a roadmap promise.
For the public narrative and interpretation of results, use the project
[About page](../site/about.html) as the main story surface.

## Purpose

LLM Quest Benchmark evaluates how LLMs make sequential choices in Space
Rangers text quests. The benchmark varies the agent harness around a model
while holding the quest environment and result logging consistent. A harness is
the wrapper that decides what context the model sees and how its response is
converted into an action: prompt template, memory strategy, tools, and loop
shape.

The core question is practical: which kinds of context help, hurt, or expose
state-tracking failures during 10-50 turn interactive fiction tasks?

The current public result should be read as a selective-intervention story, not
as a claim that larger context wrappers are universally better. Minimal prompts
remain a strong baseline on easier local quests; heavier context scaffolds are
most interesting when they recover specific stateful failures that the baseline
cannot solve.

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

Use these labels for current public descriptions of benchmark harnesses:

| Label | Harness name | Template | Memory | Tools / loop |
|---|---|---|---|---|
| Minimal prompt | `minimal` | `stub.jinja` | `DefaultMemory` | no tools, react loop |
| Short-context reasoning | `reasoning_recent` | `reasoning.jinja` | `DefaultMemory` | no tools, react loop |
| Full-history reasoning | `reasoning_full` | `reasoning.jinja` | `FullTranscriptMemory` | no tools, react loop |
| Compact memory / memo | `memo_compact` | `stateful_compact.jinja` | `CompactionMemory` | no tools, react loop |
| Prompt hints | `hinted_compact` | `stateful_compact_hints.jinja` | `CompactionMemory` | no tools, react loop |
| Tools + compact memory | `tool_compact` | `tool_augmented.jinja` | `CompactionMemory` | calculator, scratchpad, quest history |
| Tools + hints + compact memory | `tool_hinted` | `tool_augmented_hints.jinja` | `CompactionMemory` | calculator, scratchpad, quest history |
| Planner loop | `planner` | `planner.jinja` | `CompactionMemory` | plan-maintain-act loop |

Older internal experiment labels are historical and should not be presented as
the current public taxonomy.

## Current Interpretation

The strongest pattern so far is that bigger scaffolds are not automatically
better. A concise 20-word memo produced a useful sweet spot: it improved over
no-memo and full-transcript baselines, while longer or more structured memo
variants regressed. The likely mechanism is selective pressure: the short memo
forces the harness to preserve only state that matters for future decisions.

Tools and hints showed a synergy effect. Prompt hints alone hurt, and tools
alone were modest, but tools plus hints improved outcomes because the hints
pointed the model toward quantities and quest mechanics while the calculator,
scratchpad, and history search gave it ways to act on those signals.

Verbosity is a recurring failure mode. Some newer or larger models timed out
more often because they spent too much of the quest budget generating long step
responses. For sequential decision tasks, a harness that elicits concise,
actionable state updates can outperform one that invites broad reasoning.

## Implemented Runtime

- Quest execution uses the TypeScript `space-rangers-quest` submodule through
  the Python bridge in `llm_quest_benchmark/executors/ts_bridge/`.
- Environment state is exposed through `llm_quest_benchmark/environments/qm.py`.
- Agent harnesses live under `llm_quest_benchmark/harnesses/` and are selected
  by canonical snake_case harness names.
- Provider calls are normalized in `llm_quest_benchmark/llm/client.py` with
  OpenAI-compatible, Anthropic, Google, and DeepSeek adapters.
- Benchmark execution is CLI + YAML driven through `uv run llm-quest ...`.
- Static public results are generated into `site/leaderboard.json` and rendered
  by `site/index.html`.

## Metrics

Current public metrics include success rate, average steps, token/cost
statistics, and repetition rate. Repetition is interpreted as a diagnostic
signal for loopiness or context loss, not as a solved predictor of success.

Aggregate success-rate rankings should be interpreted alongside the Per Quest
view. A mode can rank well overall by solving easier quests while still failing
harder stateful, search-heavy, or navigation-heavy quests.

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
ID, harness name, run ID, outcome, and run summaries with usage/metrics.
Harness responses are parsed into a chosen action plus optional
analysis/reasoning so action validity, terminal outcome, steps, tokens/cost,
and repetition diagnostics can be regenerated from stored artifacts.
