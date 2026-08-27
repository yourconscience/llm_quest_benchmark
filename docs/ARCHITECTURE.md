# Architecture

## Overview

LLM Quest Benchmark evaluates how **agent harnesses** complete interactive
fiction quests in the Space Rangers `.qm` format. The benchmark holds the quest
environment and result logging constant while varying the harness around the
model: prompt template, memory strategy, tools, and action loop.

The runtime loop is:

1. Parse or step quest state via the TypeScript engine bridge.
2. Build harness context from current state, available choices, and memory.
3. Get a quest action from a human, random policy, or LLM-backed harness.
4. Execute the action with a recorded timestamp, record the canonical
   transition, update progress, and detect the terminal outcome.
5. Persist the schema-v2 run record to SQLite and `run_summary.json`.

## Harness Engineering Framing

This project treats the **agent harness** as the primary experimental object.
An agent harness is the wrapper around a model that controls what the model
sees, what state is carried forward, what external tools are available, and how
a raw completion is converted into a quest action. In this codebase, harnesses
are not incidental plumbing: they are the independent variable.

This follows the practical question raised by "How Much Heavy Lifting Can an
Agent Harness Do?" (arXiv:2604.07236): how much performance comes from the
surrounding scaffold rather than the base model alone? Space Rangers text
quests are useful because they are long enough to stress memory, planning, and
state tracking, but concrete enough to score with terminal success/failure
outcomes.

Closest text-game benchmarks such as TextQuests and TALE-Suite usually vary
models under a mostly fixed evaluation scaffold. LLM Quest Benchmark can hold
the model fixed and vary the harness to ask which prompt, memory, tool, and
planning choices change behavior.

## Main Runtime Layers

### 1. Quest Engine Layer

- `space-rangers-quest/`: TypeScript quest parser/player submodule.
- `llm_quest_benchmark/executors/ts_bridge/consoleplayer.ts`: Node entrypoint
  for parse/step execution.
- `llm_quest_benchmark/executors/ts_bridge/bridge.py`: Python subprocess
  bridge with startup preflight and actionable errors.

### 2. Environment Layer

- `llm_quest_benchmark/environments/qm.py`: Wraps the bridge into Python
  environment semantics (`reset`, `step`, `restore`, terminal detection). Every
  call returns a canonical `QuestSnapshot` carrying the full engine saving and a
  deterministic digest.

### 2a. Record Layer

- `llm_quest_benchmark/schemas/records.py`: `QuestAction`, `QuestSnapshot`,
  `ProgressState`, `QuestTransition`, and `RunRecord` (schema v2). These are the
  only transition/run types accepted at runtime.
- `llm_quest_benchmark/core/provenance.py`: quest checksum and engine revision
  used to gate replay and resume.
- `llm_quest_benchmark/core/progress.py`: validated YAML progress manifests and
  the monotonic progress tracker.
- `llm_quest_benchmark/core/replay.py`: transition replay, environment
  verification, and resume assembly.
- `llm_quest_benchmark/core/migration.py`: the only legacy reader, used by
  `scripts/migrate_records.py` (one-time conversion tool, not a CLI command).

### 3. Harness Layer

- `llm_quest_benchmark/harnesses/base.py`: `BaseHarness`, the shared
  LLM-backed `QuestPlayer` implementation for prompt rendering, response
  parsing, retries, contextual state, and safety filtering.
- `llm_quest_benchmark/harnesses/memory.py`: `DefaultMemory`,
  `FullTranscriptMemory`, and `CompactionMemory`.
- `llm_quest_benchmark/harnesses/tools.py`: Calculator, scratchpad, and quest
  history helpers used by tool harnesses.
- `llm_quest_benchmark/harnesses/trajectory.py`: `Trajectory`, a run-local
  retrieval/index view holding references to canonical executed
  `QuestTransition` objects for `programmatic_memory`, with bounded
  deterministic `read`/`search`. `QuestRunner` emits the same object to the
  harness, callbacks, and `QuestLogger`; `QuestLogger` serializes the persisted
  `run_summary.json` record.
- `llm_quest_benchmark/harnesses/specs.py`: canonical harness specifications
  (prompt, memory, tools, loop, reasoning) and treatment signatures.
- `llm_quest_benchmark/harnesses/backtracking.py`,
  `llm_quest_benchmark/harnesses/adaptive.py`: experimental harnesses for
  checkpoint restore and adaptive reasoning depth.
- `llm_quest_benchmark/harnesses/factory.py`: `create_harness()` and the
  implementation classes behind each specification.
- `llm_quest_benchmark/players/human.py`,
  `llm_quest_benchmark/players/random.py`: Non-LLM `QuestPlayer`
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
- `llm_quest_benchmark/core/logging.py`: Quest logger that writes complete run
  metadata before execution, persists each transition, and computes per-run
  metrics (`repetition_rate`, `bad_decision_rate`, restore statistics).
- `llm_quest_benchmark/executors/benchmark.py`: Benchmark orchestration with
  parallel workers.
- `llm_quest_benchmark/executors/cli/commands.py`: CLI commands (`run`, `play`,
  `analyze`, `analyze-run`, `benchmark`, `benchmark-report`, `leaderboard`,
  `download-quests`, `cleanup`).

### 6. Prompt Templates

- `llm_quest_benchmark/prompt_templates/`: Jinja2 templates referenced by
  harnesses.
  - `stub.jinja`: Minimal prompt.
  - `reasoning.jinja`: Short-context or full-history reasoning depending on
    harness memory.
  - `stateful_compact.jinja`: Compact memory / 20-word memo prompt.
  - `stateful_compact_hints.jinja`: Compact memo prompt with mechanics hints.
  - `memo_cot.jinja`, `memo_extended.jinja`, `memo_structured.jinja`:
    retained Exp 4 memo variants.
  - `planner.jinja`: Planner loop prompt.
  - `tool_augmented.jinja`, `tool_augmented_hints.jinja`: Tool prompts with
    compact memory, optionally with hints.
  - `programmatic_memory.jinja`: Tool prompt for bounded recent context plus
    full-fidelity `history_read`/`history_search` retrieval, no compaction.
  - `backtracking.jinja`: Choose-or-restore prompt listing restorable
    checkpoints and the remaining restore budget.
  - `adaptive_reasoning.jinja`: Concise prompt that expands into an explicit
    planning prompt when a stall or repeated state triggers deep mode.

## Persistence

Both stores hold the same logical schema-v2 record.

- `metrics.db`: `runs` (identity, quest provenance, treatment, outcome, usage,
  metrics, progress, final snapshot) and `transitions` (before snapshot,
  executed action, after snapshot, response, usage, progress, provenance,
  replay status, reasoning mode). There is no in-place upgrade from the
  pre-v2 schema; convert once with `scripts/migrate_records.py`.
- `results/<agent_id>/<quest>/run_<id>/run_summary.json`: the same record as
  JSON, written for every player type including random policies.

## Configuration

- `.env` (copied from `.env.template`): Provider API keys.
- `configs/benchmarks/`: Benchmark YAML configs defining model × harness ×
  quest matrices, optionally with `progress_manifest`.
- `configs/progress/`: Curated YAML progress manifests (`Boat.yaml` is the
  executable example).

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

Every run persists the full treatment (prompt, memory, tools, loop, reasoning,
model, temperature, system prompt, material knobs) plus a `t2_` signature
derived from that canonical data. Reports group by those components rather than
inferring them from harness names.

The harness names above are canonical snake_case identifiers used in YAML
configs, the CLI, result artifacts, and documentation. Public labels can be
friendlier, but experiment records should preserve the canonical names so runs
remain comparable.

## Experimental Harnesses (Not Yet Public)

| Label | Harness name | Template | Memory | Tools | Loop |
|---|---|---|---|---|---|
| Programmatic memory (experimental) | `programmatic_memory` | `programmatic_memory.jinja` | `DefaultMemory` | calculator, scratchpad, history_read, history_search | tool-select-then-act |
| Backtracking (experimental) | `backtracking` | `backtracking.jinja` | `CompactionMemory` | none | choose-or-restore |
| Adaptive reasoning (experimental) | `adaptive_reasoning` | `adaptive_reasoning.jinja` | `DefaultMemory` | none | adaptive-depth |

`backtracking` is the only harness that may restore a recorded checkpoint. Its
`restore_limit` knob is rejected for any other harness, restores stay visible as
transitions, and only the active checkpoint branch is truncated.
`adaptive_reasoning` starts concise and switches to a deeper planning prompt
after a repeated state or a `adaptive_stall_steps` progress stall; the reasoning
mode used is recorded on every transition.

`programmatic_memory` is an experimental treatment (see
`docs/PROGRAMMATIC_MEMORY_PROPOSAL.md`): it replaces `tool_compact`'s clipped
`quest_history` keyword search with bounded deterministic reads/searches over a
run-local `Trajectory` view of canonical executed `QuestTransition` objects, and
replaces `CompactionMemory` with `DefaultMemory` so no LLM compaction and no
full transcript run in the background. `QuestRunner` constructs each
`QuestTransition` once after an action executes, then sends that exact object to
the harness retrieval view, callbacks, and `QuestLogger` for persistence. It reuses
`ToolCompactHarness`'s tool-select-then-act call budget, so the model gets at
most one retrieval call before its final action, matching `tool_compact`.
`DefaultMemory` is the single bounded recent-context source in its select-turn
prompt; the trajectory contributes no separate recent-context block, only
on-demand `history_read`/`history_search` retrieval. It is not yet part of the
public leaderboard taxonomy.
