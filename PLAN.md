# LLM Quest Harness Engineering Plan

## Goal

Make long-running quest runs replayable, resumable, progress-aware, and attributable to an explicit harness treatment. Keep the QM environment authoritative. Backtracking is available only through a named experimental harness.

## Decisions

- Replace the existing implicit `AgentState` step record with a versioned transition record. No runtime reader accepts the old shape.
- Persist the full engine saving state and the exact transition timestamp needed by `performJump`.
- Initialize run metadata before execution. Do not patch identity/configuration after JSON export.
- Use one-time migration for old SQLite and `run_summary.json` records. Migrated records remain analyzable but are marked non-resumable when legacy data cannot prove the executed action, engine saving, or timestamp.
- Keep terminal outcome authoritative. Progress is a separate monotonic diagnostic derived from state-based milestone manifests.
- Resume restores and verifies recorded state before any new model call.
- Backtracking is a harness action with an explicit restore budget. It is not an evaluator convenience silently added to existing harnesses.
- Adaptive reasoning changes prompt depth only when a progress stall or repeated state triggers it. It does not imply unsupported provider-specific reasoning controls.
- Replace legacy template/memory inference maps with canonical harness specifications and treatment signatures.

## Canonical contracts

### Quest action

A quest action is one of:

- `choose`: one-based choice index plus the recorded `performed_at_ms` used by the engine transition.
- `restore`: checkpoint index selected by the backtracking harness.

### Quest snapshot

A snapshot contains:

- location ID;
- observation text;
- available choices with stable IDs and text;
- parameter-state text;
- reward, termination state, and authoritative engine game state;
- full JSON-serializable engine saving;
- a deterministic digest over canonical state fields.

### Quest transition

A transition contains:

- monotonic transition index;
- before snapshot;
- executed quest action;
- after snapshot;
- agent response and usage;
- progress state after execution;
- provenance and replay status.

Terminal state is the `after` snapshot of the final executed transition. It is not a synthetic decision row.

### Run record v2

`run_summary.json` and SQLite contain the same logical record:

- `schema_version: 2`;
- run identity and timestamps;
- quest path, checksum, language, and engine revision;
- canonical treatment description and signature;
- resume lineage;
- outcome, usage, metrics, and final snapshot;
- explicit transitions.

## Existing-record mapping

The migration command accepts a legacy JSON file/directory or SQLite database and writes a separate v2 destination.

For each legacy decision row:

1. Build `before` from its location, observation, and choices.
2. Use the next legacy row as `after` only when it is structurally the next observed state.
3. Use `final_state` for the last `after` when available.
4. Treat the logger-only terminal pseudo-step as terminal state, not as an executed action.
5. Prefer SQLite `steps.action` over compact JSON `llm_decision.choice`, because old compact JSON could persist the model proposal rather than the runner-clamped action.
6. Mark missing parameter state, engine saving, timestamp, choice ID, or post-state as unavailable. Never invent values.
7. Set migrated transition provenance to `legacy_mapped` and replay status to `unavailable` unless all deterministic inputs exist.
8. Recompute usage and metrics from mapped transitions.
9. Derive the treatment from legacy agent config and the canonical harness registry. Unknown configurations receive an explicit `unknown` component, not a compatibility alias.

The runtime, analyzers, reports, and site consume only v2 after cutover.

## Implementation sequence

### 1. Data model and engine protocol

- Add action, snapshot, progress, transition, treatment, and run-record schema types.
- Extend `QMBridgeState` with authoritative game state and full engine saving.
- Change the TypeScript bridge protocol to accept structured choose/restore commands.
- Pass the recorded transition timestamp to `performJump` instead of generating it inside the bridge.
- Add exact `loadSaving` support and snapshot digest verification.
- Replace `AgentState` callbacks and trajectory storage with canonical transitions.

Acceptance:

- A choose transition round-trips through JSON without losing choice IDs, saving state, timestamp, or executed action.
- Loading a saving reproduces the recorded digest.
- No synthetic terminal decision is emitted.

### 2. Persistence cutover and migration

- Replace legacy SQLite tables with v2 run and transition tables.
- Remove column-addition, old-column fallback, post-run config patching, and random-run JSON suppression.
- Export one v2 `run_summary.json` for every player type.
- Update analyzers, reports, leaderboard generation, replay scripts, trace import/export, and CLI inspection to v2.
- Add `scripts/migrate_records.py --source PATH --output PATH` for JSON trees and SQLite databases.
- Update human/web trace export to retain restore events rather than erasing undone transitions.

Acceptance:

- A legacy fixture maps deterministically to the expected v2 record.
- Unknowable fields are marked unavailable and the record is rejected for resume.
- Current runs write no legacy fields or tables.

### 3. Replay and resume

- Add transition replay that executes recorded choose timestamps and restore actions and compares each resulting digest.
- Add `llm-quest run --resume-from PATH`.
- Resume loads quest and treatment from the record, verifies quest checksum and engine revision, rebuilds harness memory from transitions, restores the active checkpoint, then makes the next agent call.
- Add a resumable `TRUNCATED` outcome for explicit step limits.
- Link resumed runs to their source run and preserve prior transitions.

Acceptance:

- Replay of an unchanged record verifies every transition.
- Any quest checksum, action, timestamp, or state mutation fails before model inference.
- A truncated run resumes and reaches the same state as an uninterrupted deterministic run.

### 4. Structured progress

- Add a validated YAML progress manifest covering quest milestone predicates.
- Match milestones against location ID, parameter-state contents, and engine game state.
- Track current progress, maximum progress, newly reached milestones, and stalled transition count.
- Include a state-based Boat manifest as the executable example.
- Expose `progress_manifest` in benchmark configuration and recover it from a resume record.

Acceptance:

- Progress is monotonic even after restore.
- Terminal success yields 100 percent.
- Missing manifests fall back to terminal-only progress without guessing story advancement.

### 5. Canonical harness treatments

- Replace the class-only harness registry with specifications that declare prompt, memory, tools, loop, and reasoning policy.
- Generate treatment signatures from canonical JSON plus model and material knobs.
- Remove legacy template/memory compatibility maps and config-key shims.
- Persist the full treatment before the first transition.

Acceptance:

- Materially different harness configurations have different signatures.
- Equivalent configurations serialize and hash identically.
- Reports group by treatment components without inferring them from names.

### 6. Backtracking harness

- Add the `backtracking` harness and a prompt/action parser that can choose or restore a checkpoint.
- Add `restore_limit`, valid only for this harness.
- Track restore attempts, accepted restores, restored distance, and progress recovered.
- Preserve the full chronological transition log while maintaining a separate active branch checkpoint stack.

Acceptance:

- Restore loads the exact recorded saving and truncates only the active branch.
- Restore events remain visible in persisted transitions and human/web traces.
- Existing harnesses cannot emit restore actions.

### 7. Adaptive reasoning harness

- Add the `adaptive_reasoning` harness.
- Use concise reasoning by default and a deeper planning prompt after repeated state or progress stall.
- Add `adaptive_stall_steps`, valid only for this harness.
- Persist the reasoning mode used on every transition.

Acceptance:

- Routine states use concise mode.
- The configured trigger switches the next decision to deep mode.
- Recovery resets the stall trigger without losing history.

### 8. Verification and documentation

- Update README, architecture, specification, CLI help/examples, configs, and public trace documentation.
- Run the complete Python suite and JavaScript build.
- Run a random-policy Boat quest end to end and inspect its v2 record.
- Migrate a legacy JSON and SQLite fixture.
- Truncate and resume a deterministic Boat run.
- Exercise a restore action against the real QM bridge.

## Non-goals

- Supporting legacy runtime schemas or legacy configuration keys after migration.
- Replacing the QM engine with Gymnasium, OpenEnv, Inspect, or Harbor.
- Adding remote environment services, RL training, model graders, or automatic milestone generation.
- Claiming progress metrics are comparable across quests without curated manifests.
- Enabling backtracking for existing public harnesses.

## Risks and controls

- Engine randomness: record and replay the exact `performed_at_ms` and full saving.
- Legacy ambiguity: mark it; do not infer a resumable state.
- Resume contamination: verify quest checksum, engine revision, treatment, and state before inference.
- Bundled treatment effects: persist component-level treatment data and keep new harnesses separately named.
- Cost growth: adaptive deep mode is trigger-bound; backtracking has an explicit restore limit.
- Public metric drift: keep terminal outcome primary and progress diagnostic until manifests are reviewed.
