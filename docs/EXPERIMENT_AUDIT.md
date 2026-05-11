# Experiment Audit

Generated: 2026-05-11

Sources reviewed:

- `docs/EXPERIMENTS_LOG.md`
- `docs/ARCHITECTURE.md`
- `configs/benchmarks/*.yaml`
- `site/leaderboard.json`

This audit uses the post-refactor harness taxonomy: `minimal`,
`reasoning_recent`, `reasoning_full`, `memo_compact`, `hinted_compact`,
`tool_compact`, `tool_hinted`, and `planner`.

## Experiment Inventory

| Experiment | Config / source | Harness mapping | Quest scope | Completed runs recorded in log | Audit disposition |
|---|---|---|---|---:|---|
| Exp 2: Memory Modes | `memory_full_transcript.yaml`, `memory_compaction.yaml` | `reasoning_full`, `memo_compact` | 14 historical quests including `Prison` | 126 | Unreliable for canonical comparison: loop-breaker bug era. |
| Exp 3 Arm 1: No Loop Breaker | `exp3_no_loop_breaker.yaml` | `reasoning_full` | 18 quests, excluding `Boat`/`Prison` | 36 | Use only rerun after timeout fix; pre-fix attempt is noisy/incomplete. |
| Exp 3 Arm 2: Stateful Compact | `exp3_stateful_compact.yaml` | `memo_compact` | 18 quests, excluding `Boat`/`Prison` | 36 | Canonical memo baseline, but only 2 runs/quest. |
| Exp 4: Compaction No Memo | `exp4_compaction_no_memo.yaml` | retired ablation, not canonical | 18 quests | 36 | Do not aggregate into `memo_compact`. |
| Exp 4: Memo Extended | `exp4_memo_extended.yaml` | retired `memo_extended` variant | 18 quests | 36 | Non-canonical variant. |
| Exp 4: Memo Structured | `exp4_memo_structured.yaml` | retired `memo_structured` variant | 18 quests | 36 | Non-canonical variant. |
| Exp 4: Memo CoT | `exp4_memo_cot.yaml` | retired `memo_cot` variant | 18 quests | 36 | Non-canonical variant. |
| Exp 5: Baseline Variance | `exp5_stateful_compact_variance.yaml` | `memo_compact` | 18 quests | 90 | Canonical memo baseline variance study. |
| Exp 6: Prompt Hints | `exp6_prompt_hints.yaml` | `hinted_compact` | 18 quests | 54 | Canonical single-model harness comparison. |
| Exp 6: Tools | `exp6_tools.yaml` | `tool_compact` | 18 quests | 54 | Canonical single-model harness comparison. |
| Exp 6: Tools + Hints | `exp6_tools_hints.yaml` | `tool_hinted` | 18 quests | 54 | Canonical single-model harness comparison. |
| Exp 7: Multi-Model Comparison | `exp7_*.yaml` | `memo_compact` | 5 winnable quests | 75 | Canonical model sweep for memo harness. |
| Exp 7b: Model Upgrades | `exp7b_model_upgrades.yaml` | `memo_compact` | 18 quests | 108 | Noisy model-upgrade sweep; high timeout rates for Qwen 3.6 and Haiku 4.5. |

## 1. Harness Coverage Matrix

The table below is computed from `site/leaderboard.json` and counts recorded
leaderboard runs by harness and quest. `Boat` and `Prison` are retained in this
matrix because they still appear in the published leaderboard data, but they
are retired from the canonical experiment set.

| Harness | Badday | Banket | Boat | Codebox | Depth | Driver | Edelweiss | Election | Foncers | Leonardo | Ministry | Pizza | Prison | Robots | Ski | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `minimal` | 22 | 22 | 23 | 22 | 22 | 22 | 22 | 22 | 22 | 22 | 22 | 22 | 22 | 22 | 22 | 331 |
| `reasoning_recent` | 22 | 22 | 28 | 22 | 22 | 24 | 25 | 30 | 25 | 25 | 26 | 22 | 28 | 31 | 31 | 383 |
| `reasoning_full` | 17 | 17 | 9 | 17 | 17 | 15 | 17 | 17 | 17 | 17 | 16 | 17 | 6 | 14 | 14 | 227 |
| `memo_compact` | 37 | 39 | 18 | 39 | 39 | 39 | 39 | 37 | 39 | 37 | 39 | 37 | 15 | 39 | 34 | 527 |
| `hinted_compact` | 4 | 4 | 1 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 1 | 4 | 4 | 54 |
| `tool_compact` | 3 | 3 | **0** | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | **0** | 3 | 3 | 39 |
| `tool_hinted` | 3 | 3 | **0** | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | **0** | 3 | 3 | 39 |
| `planner` | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 15 |

Leaderboard scope note: the current public JSON includes 15 quest columns and
does not include several 18-quest experiment-log quests such as `Pilot`,
`Disk`, `Player`, `Shashki`, and `Sortirovka1`. Those quests appear in the
benchmark configs and experiment log, so a future leaderboard refresh should
either add them or explicitly document why the public slice excludes them.

## 2. Gap Analysis

### Zero-run harness × quest cells

All zero-run cells in the published leaderboard matrix are retired quest cells:

- `tool_compact` × `Boat`: 0 runs.
- `tool_compact` × `Prison`: 0 runs.
- `tool_hinted` × `Boat`: 0 runs.
- `tool_hinted` × `Prison`: 0 runs.

Because `Boat` and `Prison` are retired, these do not require new canonical
runs. They do indicate that the public leaderboard mixes active and retired
quest scopes.

### Fewer than 3 runs

- `hinted_compact` × `Boat`: 1 run; retired quest.
- `hinted_compact` × `Prison`: 1 run; retired quest.
- `planner`: 1 run on every published quest (`Badday`, `Banket`, `Boat`,
  `Codebox`, `Depth`, `Driver`, `Edelweiss`, `Election`, `Foncers`,
  `Leonardo`, `Ministry`, `Pizza`, `Prison`, `Robots`, `Ski`).

Canonical action item: the planner harness has insufficient variance coverage.
For active quests, it needs at least two additional runs per quest to reach the
minimum 3-run threshold.

### Only 1 model tested

The following harnesses have leaderboard cells where the run count may be at
least 3, but the model dimension is still only one model. These cells cannot
separate harness effects from model-specific behavior:

- `tool_compact`: one model on all non-retired published quests
  (`Badday`, `Banket`, `Codebox`, `Depth`, `Driver`, `Edelweiss`, `Election`,
  `Foncers`, `Leonardo`, `Ministry`, `Pizza`, `Robots`, `Ski`).
- `tool_hinted`: one model on all non-retired published quests
  (`Badday`, `Banket`, `Codebox`, `Depth`, `Driver`, `Edelweiss`, `Election`,
  `Foncers`, `Leonardo`, `Ministry`, `Pizza`, `Robots`, `Ski`).
- `planner`: one model on every published quest and only one run per quest.
- `hinted_compact` on `Boat` and `Prison`: one model, but both quests are
  retired.

The stronger public comparison cells are `minimal`, `reasoning_recent`,
`reasoning_full`, and `memo_compact`, which have multi-model coverage in the
leaderboard data. However, `reasoning_full` and `memo_compact` still require
provenance filtering because early memory-mode runs overlap with the loop-
breaker bug era.

## 3. Noise / Anomaly List

### Loop-breaker bug era

- Exp 2 memory-mode runs are unreliable. The experiment log documents a
  number-normalization bug in `_normalize_for_signature` and aggressive loop
  breaker overrides that changed correct model decisions.
- Exp 3 Arm 1 has a pre-fix/incomplete attempt affected by SDK timeout issues.
  Only the rerun after the timeout fix should be considered.
- Any leaderboard entry whose provenance traces to Exp 2 or the Exp 3 pre-fix
  attempt should be marked non-canonical until regenerated or excluded.

### High timeout runs

- Exp 7b `Qwen 3.6 Flash`: 17/36 timeouts (47%).
- Exp 7b `Claude Haiku 4.5`: 19/36 timeouts (53%).
- Exp 7b `DeepSeek V4 Flash`: 5/36 timeouts (14%), below the >30% threshold
  but still noisy because success was 0/36.

The Qwen 3.6 and Haiku 4.5 rows should be interpreted primarily as timeout /
verbosity failures, not clean harness-quality signals.

### Retired quests

- `Boat`: trivial / smoke-test-like quest; removed from canonical experiment
  configs.
- `Prison`: loops endlessly; removed from canonical experiment configs.

Both still appear in `site/leaderboard.json`, so public summaries should label
them as retired or remove them from canonical aggregates.

### Retired harness variants

The following Exp 4 arms are not part of the final taxonomy and should not be
merged into canonical `memo_compact` results:

- `memo_extended`
- `memo_structured`
- `memo_cot`
- `compaction_no_memo` ablation

Current YAML files have been migrated to the `harness:` key, so historical
variant identity must be preserved from `docs/EXPERIMENTS_LOG.md` and config
file names rather than inferred only from the post-refactor `harness` field.

## 4. Budget Estimate

Top-priority new runs to close actionable gaps while avoiding retired quests:

| Priority | Harness | Quest(s) | New runs needed | Reason |
|---:|---|---|---:|---|
| 1 | `planner` | 13 active published quests (`Badday`, `Banket`, `Codebox`, `Depth`, `Driver`, `Edelweiss`, `Election`, `Foncers`, `Leonardo`, `Ministry`, `Pizza`, `Robots`, `Ski`) | 26 | Bring 1-run planner cells up to the 3-run minimum on active leaderboard quests. |
| 2 | `planner` | Same 13 active published quests | 39 | Add a second model with 3 runs/quest so planner effects are not single-model artifacts. |
| 3 | `tool_compact` | Same 13 active published quests | 39 | Add a second model with 3 runs/quest; current cells are all one-model results. |
| 4 | `tool_hinted` | Same 13 active published quests | 39 | Add a second model with 3 runs/quest; current cells are all one-model results. |
| 5 | Public leaderboard refresh | `Pilot`, `Disk`, `Player`, `Shashki`, `Sortirovka1` | Scope-dependent | These quests are present in canonical 18-quest configs/logs but absent from the current public leaderboard matrix. Backfill or explicitly exclude them. |

Do not spend new budget on `Boat` or `Prison` unless the goal is only to
reproduce historical/public rows; both are retired from canonical analysis.

## 5. Leaderboard Integrity

Findings from `site/leaderboard.json`:

1. The leaderboard uses the eight canonical public modes and does not expose
   retired harness variants as separate modes. This is good, but it creates a
   provenance risk if Exp 4 retired variants were ever aggregated under
   `memo_compact`.
2. `Boat` and `Prison` remain in the published quest list despite being retired
   from canonical experiment configs. They should be excluded from aggregate
   claims or clearly labeled as retired.
3. `planner` has only one run per quest and one model. It should not be used for
   reliability claims yet.
4. `tool_compact` and `tool_hinted` have three runs per active published quest,
   but only one model. Their harness comparison is promising but not yet
   model-robust.
5. Published `reasoning_full` / `memo_compact` rows need run-level provenance
   checks before canonical use because early memory-mode experiments overlap
   with the Exp 2 loop-breaker bug era.
6. Exp 7b model-upgrade entries for `Qwen 3.6 Flash` and `Claude Haiku 4.5`
   should be annotated as high-timeout data if included in any leaderboard or
   narrative comparison.

Recommended integrity rule: canonical leaderboard aggregates should require
non-retired quests, canonical harness names, no loop-breaker bug provenance, at
least 3 runs per harness × quest cell, and at least two models for claims about
harness effects rather than model effects.
