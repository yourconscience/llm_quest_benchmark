# SPEC: Replayable Harness Evaluation

## Goal

LLM Quest Benchmark evaluates the model-harness pair on sequential Space
Rangers choices while holding the QM environment fixed. A run must be:

- attributable to an explicit prompt, memory, tool, loop, and reasoning
  treatment;
- recorded as exact environment transitions;
- resumable when its engine state is complete and verified;
- diagnosable through terminal outcome, curated progress, and transcript
  metrics.

The current research question remains: which harness interventions recover
state-tracking, planning, exploration, and memory failures during long-running
interactive fiction?

## User-visible behavior

### Run records

Every human, random, or LLM run writes a schema-v2 `run_summary.json` and the
same logical data to SQLite. Each transition records:

- the complete state before the action;
- the executed choose or restore action;
- the complete state after the action;
- the agent response and usage;
- progress and replay provenance.

The final environment state is the final transition's `after` state. Terminal
states are not represented as fake agent decisions.

### Replay and resume

`llm-quest run --resume-from PATH` loads the quest and treatment from a v2 run,
verifies the quest checksum, engine revision, recorded transitions, and active
checkpoint, then continues without losing harness memory.

Explicit step limits produce `TRUNCATED`, which is resumable. Divergent or
legacy-mapped records fail before a new model call.

### Existing records

`llm-quest migrate-records --source PATH --output PATH` maps legacy
`run_summary.json` trees and SQLite databases into schema v2. Migration is the
only legacy reader.

Migration never fabricates missing action, timestamp, parameter, saving, or
post-state data. Records lacking deterministic state remain analyzable and are
marked non-resumable.

### Progress

A benchmark may declare `progress_manifest`, a validated YAML file of
quest-specific state predicates and percentages. Runtime progress includes:

- current and maximum progress;
- newly reached milestones;
- transitions since the last new milestone.

Progress is monotonic across restores. Terminal success is always 100 percent.
Without a manifest, progress is terminal-only.

### Harness treatments

The harness registry declares the material components of each treatment:

- prompt;
- memory;
- tools;
- loop;
- reasoning policy.

The persisted treatment signature is derived from canonical component data,
model, temperature, and material harness knobs. Reports use this data directly
and do not infer components from harness names.

### Backtracking

The experimental `backtracking` harness may either choose a current option or
restore a recorded checkpoint. `restore_limit` applies only to this harness.
Restores retain chronological history and truncate only the active branch.
Existing harnesses cannot restore.

### Adaptive reasoning

The experimental `adaptive_reasoning` harness uses concise reasoning by
default. It switches to a deeper planning prompt after repeated state or a
configured progress stall. `adaptive_stall_steps` applies only to this harness,
and every transition records the reasoning mode used.

## Acceptance tests

1. A real Boat transition round-trips without losing choice IDs, full engine
   saving, timestamp, executed action, or state digest.
2. Exact engine saving restore reproduces the recorded digest.
3. Replay detects any changed quest, action, timestamp, or resulting state
   before model inference.
4. A truncated deterministic run resumes to the same state as an uninterrupted
   run.
5. A legacy JSON fixture and SQLite fixture map into v2; ambiguous fields are
   explicitly unavailable and prevent resume.
6. All player types persist v2 JSON; random runs are not suppressed.
7. Progress milestones are state-based, monotonic, and separate from terminal
   outcome.
8. A real restore returns to the selected checkpoint and remains visible as a
   transition.
9. Backtracking and adaptive-only knobs are rejected for other harnesses.
10. Treatment signatures are stable for equivalent configs and distinct for
    material differences.
11. Existing analyzers, reports, leaderboard generation, replay scripts, and
    web/human traces consume only v2.
12. The Python suite, JavaScript build, random Boat smoke, migration smoke,
    resume smoke, and restore smoke pass.

## Constraints

- Python 3.11 is the supported local runtime for the locked dependency set.
- The TypeScript `space-rangers-quest` engine remains authoritative for game
  state and win/fail outcome.
- The environment remains unchanged for public harness comparisons.
- Backtracking is an explicit experimental capability, not evaluator behavior.
- Deterministic replay uses the full engine saving and the original transition
  timestamp passed to `performJump`.
- Existing public outcome metrics remain comparable; progress is diagnostic
  until manifests are curated.
- No legacy config aliases, database fallbacks, dual record writers, or runtime
  schema adapters remain after cutover.

## Non-goals

- OpenEnv, Gymnasium, Inspect, Harbor, remote environment, or RL integration.
- Automatically generating or model-grading progress milestones.
- Making every historical record resumable.
- Treating more context, more reasoning, or backtracking as universally better.
- Changing quest authoring or the upstream `.qm` format.

## Dependencies and integrations

- `space-rangers-quest` supplies parser, state transition, saving, and outcome
  semantics through the TypeScript bridge.
- YAML benchmark configuration supplies an optional progress manifest.
- SQLite and `run_summary.json` store the same schema-v2 logical record.
- Existing static reports and the web player remain publication surfaces after
  their v2 cutover.

## Risks

- Legacy compact JSON can contain the model-proposed action rather than the
  runner-executed action. Migration prefers SQLite and otherwise marks the
  action unverified.
- Legacy records omit full engine saving and transition timestamps, so most are
  not resumable.
- Dynamic quest behavior can diverge if timestamps are regenerated. The bridge
  therefore receives the recorded timestamp.
- Restore can inflate apparent capability. It has a separate harness name,
  explicit budget, and restore metrics.
- Adaptive reasoning can hide extra inference cost. Reasoning mode and usage
  remain visible per transition.

## Codebase notes

- Detailed implementation order and mapping rules live in `PLAN.md`.
- `QMPlayerEnv` and `QMBridge` own environment snapshots and saving restore.
- `QuestRunner` owns active checkpoints, replay verification, and transition
  construction.
- `QuestLogger` persists completed transitions and run metadata initialized
  before execution.
- Harness specifications and treatment signatures are canonical in the harness
  registry/configuration layer.

## Outcome / Deviations

Implemented as a single schema-v2 cutover. No runtime reader accepts a pre-v2
record; `llm-quest migrate-records` is the only legacy reader.

Delivered:

- Canonical `QuestAction`, `QuestSnapshot`, `ProgressState`, `QuestTransition`,
  and `RunRecord` types in `llm_quest_benchmark/schemas/records.py`.
- Structured TypeScript bridge protocol (`state` / `jump` / `load`) carrying the
  full engine saving; `performedAtMs` is supplied by the caller and never
  generated inside the bridge.
- `QMPlayerEnv.restore()` with digest verification, and a snapshot digest over
  location, observation, choices, parameter state, terminal state, and saving.
- v2 SQLite (`runs`, `transitions`) plus one `run_summary.json` per run for
  every player type, with run metadata written before execution.
- `llm-quest migrate-records` for legacy JSON trees and SQLite databases.
- `llm-quest run --resume-from`, replay verification, and the resumable
  `TRUNCATED` outcome.
- Validated YAML progress manifests with a state-based `configs/progress/Boat.yaml`.
- Canonical harness specifications and `t2_` treatment signatures.
- Experimental `backtracking` and `adaptive_reasoning` harnesses.

Implementation details:

1. **Progress fields.** `ProgressState.current` is the monotonic achieved
   percentage and `maximum` is the manifest ceiling. `scored` distinguishes a
   curated manifest from terminal-only progress.
2. **Deterministic engine inputs.** The TypeScript player starts from a stable
   quest-derived seed. The runner derives `performedAtMs` from the quest
   checksum and transition index, then persists it. Independent runs with the
   same actions therefore reproduce the same state, and replay compares exact
   snapshot digests.
3. **Web trace timestamps.** The browser player's engine timestamp is not
   observable from the page. Human web traces record `performed_at_ms: null`
   and `replay_status: unavailable`; they still retain full savings, abandoned
   branches, and explicit restore transitions.
4. **`progress_recovered`.** This diagnostic is the monotonic progress gained
   after the last accepted restore. Individual restore effects remain
   recoverable from transitions.
5. **Leaderboard labels.** Friendly mode labels are presentation derived from
   canonical treatment components. Persisted identity and grouping use the
   treatment signature; no runtime reader accepts legacy record shapes.

Verified:

- `uv run pytest`: 370 passed, 4 skipped.
- `uv run ruff check .`: passed.
- `pnpm run build`: passed.
- Existing SQLite data migrated: 8 runs and 73 transitions; all correctly
  marked non-resumable because legacy records lack deterministic engine state.
- A real random-policy Boat run wrote a nested schema-v2 record, truncated at
  four transitions, replayed those transitions exactly, resumed to six, and
  preserved lineage and progress.
