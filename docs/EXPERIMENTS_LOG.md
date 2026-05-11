# Experiments Log

## Harness Name Mapping

| Experiment arm | Old label | New harness name |
|---|---|---|
| Minimal prompt arms | `stub` | `minimal` |
| Short-context reasoning arms | `reasoning` + `default` memory | `reasoning_recent` |
| Full-history reasoning arms | `reasoning` + `full_transcript` memory | `reasoning_full` |
| Stateful compact memo arms | `stateful_compact` + compaction | `memo_compact` |
| Hinted compact memo arms | `stateful_compact_hints` + compaction | `hinted_compact` |
| Tool-augmented compact arms | `tool_augmented` + compaction | `tool_compact` |
| Tool-augmented hinted arms | `tool_augmented_hints` + compaction | `tool_hinted` |
| Planner arms | `planner` | `planner` |
| Memo variation arms | `memo_extended`, `memo_structured`, `memo_cot` | retired experiment variants, not canonical harnesses |

> Historical / non-authoritative notes. This log preserves experiment history
> and branch-era shorthand. For the current public taxonomy and public
> comparison slice, use `site/about.html`, `site/leaderboard.json`,
> `docs/ARCHITECTURE.md`, and `docs/DATASHEET.md`.

Record of benchmark experiments, findings, and decisions. Keeps history out of source code.

## Current Coverage Audit (2026-05-11)

Sources reviewed for this audit:

- `docs/EXPERIMENTS_LOG.md`
- `docs/ARCHITECTURE.md`
- `configs/benchmarks/*.yaml`
- `site/leaderboard.json`

This audit uses the post-refactor harness taxonomy: `minimal`,
`reasoning_recent`, `reasoning_full`, `memo_compact`, `hinted_compact`,
`tool_compact`, `tool_hinted`, and `planner`.

### Experiment Inventory

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

### Harness Coverage Matrix

The table below is computed from `site/leaderboard.json` and counts recorded
leaderboard runs by harness and quest. `Boat` and `Prison` are retained because
they still appear in the published leaderboard data, but they are retired from
the canonical experiment set.

| Harness | Badday | Banket | Boat | Codebox | Depth | Driver | Edelweiss | Election | Foncers | Leonardo | Ministry | Pizza | Prison | Robots | Ski | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `minimal` | 22 | 22 | 23 | 22 | 22 | 22 | 22 | 22 | 22 | 22 | 22 | 22 | 22 | 22 | 22 | 331 |
| `reasoning_recent` | 22 | 22 | 28 | 22 | 22 | 24 | 25 | 30 | 25 | 25 | 26 | 22 | 28 | 31 | 31 | 383 |
| `reasoning_full` | 17 | 17 | 9 | 17 | 17 | 15 | 17 | 17 | 17 | 17 | 16 | 17 | 6 | 14 | 14 | 227 |
| `memo_compact` | 37 | 39 | 18 | 39 | 39 | 39 | 39 | 37 | 39 | 37 | 39 | 37 | 15 | 39 | 34 | 527 |
| `hinted_compact` | 4 | 4 | 1 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 1 | 4 | 4 | 54 |
| `tool_compact` | 3 | 3 | 0 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 0 | 3 | 3 | 39 |
| `tool_hinted` | 3 | 3 | 0 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 0 | 3 | 3 | 39 |
| `planner` | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 15 |

Leaderboard scope note: the current public JSON includes 15 quest columns and
does not include several 18-quest experiment-log quests such as `Pilot`,
`Disk`, `Player`, `Shashki`, and `Sortirovka1`. A future leaderboard refresh
should either add them or explicitly document why the public slice excludes
them.

### Gap Analysis

All zero-run cells in the published leaderboard matrix are retired quest cells:

- `tool_compact` x `Boat`: 0 runs.
- `tool_compact` x `Prison`: 0 runs.
- `tool_hinted` x `Boat`: 0 runs.
- `tool_hinted` x `Prison`: 0 runs.

Because `Boat` and `Prison` are retired, these do not require new canonical
runs. They do indicate that the public leaderboard mixes active and retired
quest scopes.

Cells with fewer than 3 runs:

- `hinted_compact` x `Boat`: 1 run; retired quest.
- `hinted_compact` x `Prison`: 1 run; retired quest.
- `planner`: 1 run on every published quest.

Canonical action item: the planner harness has insufficient variance coverage.
For active quests, it needs at least two additional runs per quest to reach the
minimum 3-run threshold.

The following harnesses have leaderboard cells where the run count may be at
least 3, but the model dimension is still only one model: `tool_compact`,
`tool_hinted`, and `planner`. Their comparison is promising, but not yet
model-robust.

### Noise And Anomalies

Loop-breaker bug era:

- Exp 2 memory-mode runs are unreliable. The experiment log documents a
  number-normalization bug in `_normalize_for_signature` and aggressive loop
  breaker overrides that changed correct model decisions.
- Exp 3 Arm 1 has a pre-fix/incomplete attempt affected by SDK timeout issues.
  Only the rerun after the timeout fix should be considered.
- Any leaderboard entry whose provenance traces to Exp 2 or the Exp 3 pre-fix
  attempt should be marked non-canonical until regenerated or excluded.

High-timeout model-upgrade runs:

- Exp 7b `Qwen 3.6 Flash`: 17/36 timeouts (47%).
- Exp 7b `Claude Haiku 4.5`: 19/36 timeouts (53%).
- Exp 7b `DeepSeek V4 Flash`: 5/36 timeouts (14%), below the >30% threshold
  but still noisy because success was 0/36.

Retired quests:

- `Boat`: trivial / smoke-test-like quest; removed from canonical experiment
  configs.
- `Prison`: loops endlessly; removed from canonical experiment configs.

Retired harness variants:

- `memo_extended`
- `memo_structured`
- `memo_cot`
- `compaction_no_memo` ablation

These variants should not be merged into canonical `memo_compact` results.

### Budget Estimate

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

### Leaderboard Integrity

Recommended integrity rule: canonical leaderboard aggregates should require
non-retired quests, canonical harness names, no loop-breaker bug provenance, at
least 3 runs per harness x quest cell, and at least two models for claims about
harness effects rather than model effects.

## Exp 2: Memory Modes (2026-04-27)

**Config**: `configs/benchmarks/memory_full_transcript.yaml`, `configs/benchmarks/memory_compaction.yaml`
**Models**: Gemini 2.5 Flash, Claude Haiku 4.5, GPT-5.4 Mini
**Quests**: 14 quests (Badday through Ski + Prison)

### Findings

- Overall success rate: 7.1% (9/126 runs)
- Full transcript mode: model sees all past observations, no state tracking output needed
- Compaction mode: periodic LLM summarization every N steps; state tracking in output is needed to preserve facts through compaction cycles

### Lessons

- Very low success rate prompted deep failure analysis (see `research/error_analysis.md`)

## Exp 2.5: Failure Analysis (2026-04-27)

Manual analysis of 33 failure traces from Gemini Flash full_transcript runs.

### Root cause: Loop breaker

The `_apply_loop_breaker` mechanism was overriding correct LLM decisions. Evidence:
- ~144 loop breaker overrides across 33 traces
- 13+ failures directly caused by forced action changes
- **Number normalization bug**: `re.sub(r"\d+", "<num>")` in `_normalize_for_signature` replaced all digits, making "HP:80" and "HP:53" hash identically. Nearly every combat/economy state triggered the loop breaker.
- Threshold of 1 meant any revisited state signature triggered an override on the second visit

### Decision

- **Disabled loop breaker** entirely in all agent types (llm_agent, planner_agent, tool_agent)
- **Removed number normalization** from state signature computation
- Kept `_state_action_counts` and `_state_signature` (used by safety filter and loop escape)
- Removed `_apply_loop_breaker` method and `_loop_repetition_threshold` field as dead code

### Other findings

- Terminal game observation was never logged (runner logged pre-action state only). Fixed: added terminal step logging in runner.py with observation fallback.
- Boat quest too easy (trivial), Prison quest loops endlessly. Both removed from experiment configs.

## Exp 3: No Loop Breaker + Stateful Compact (2026-04-28)

**Branch**: `exp3-disable-loop-breaker` (PR #25)
**Model**: Gemini 3 Flash Preview (via OpenRouter)
**Quests**: 18 quests (13 original minus Boat/Prison + 5 new easier candidates)

### Design

Two arms, 2 runs per quest:
- **Arm 1** (full_transcript + reasoning template): Clean baseline without loop breaker. Tests whether removing the loop breaker improves success rate.
- **Arm 2** (compaction + stateful_compact template): Tests memo-based state tracking with periodic compaction at 50-step intervals.

### Config changes
- `configs/benchmarks/exp3_no_loop_breaker.yaml` - Arm 1
- `configs/benchmarks/exp3_stateful_compact.yaml` - Arm 2
- New template: `prompt_templates/stateful_compact.jinja` with `memo` output field

### Issue: OpenAI SDK timeout

First run attempt took 10+ hours and only completed 36% of runs. Root cause: OpenAI Python SDK default read timeout is 600s with 2 retries. When OpenRouter connections stalled, a single API call could block for 16-32 minutes. Fix: set `max_retries=0` on SDK client (our own retry wrapper handles retries) and reduce timeout from 600s to 30s.

### Results (re-run with timeout fix, 65 min each)

| Arm | Wins | Rate | Cost | Won quests |
|---|---|---|---|---|
| no_loop_breaker (full_transcript + reasoning) | 2/36 | 5.6% | $4.46 | Ski, Disk |
| stateful_compact (compaction + 20w memo) | 6/36 | 16.7% | $3.27 | Pilot x2, Disk, Election, Sortirovka1 x2 |

### Failure analysis

- **Memo field empty 100% of steps in no_loop_breaker arm** - reasoning.jinja doesn't instruct memo usage
- **stateful_compact 3x better**: memo kept signals salient (e.g. "Hogger is greedy" in Pilot), enabled numeric dashboards in Sortirovka1
- **31% fewer prompt tokens** with compaction vs full_transcript, zero parse regressions
- **Root causes of remaining failures**: numeric optimization blindness (Pizza, Banket), spatial puzzle inability (Codebox, Shashki), health race undetected (Badday skipped bell mechanic), RNG-dependent outcomes (Disk riddle randomization)

## Exp 4: Memo Variations (2026-04-28)

**Branch**: `exp4-memo-variations` (PR #26)
**Model**: Gemini 3 Flash Preview (via OpenRouter)
**Quests**: Same 18 quests as exp3
**Hypothesis**: Memo quality is the bottleneck. Test whether more space, structured format, or more compute improves on the 20-word baseline.

### Design

Four arms, 2 runs per quest, all using compaction mode (interval 50):

| Arm | Template | Memo budget | Reasoning budget | Tests |
|---|---|---|---|---|
| compaction_no_memo | reasoning.jinja | none | 25w | ablation: is memo or compaction the key? |
| memo_extended | memo_extended.jinja | 50w generic | 50w | is space the bottleneck? |
| memo_structured | memo_structured.jinja | 50w structured (HP:X Money:Y Trend:+/-) | 50w | does format help? |
| memo_cot | memo_cot.jinja | 30w + 100w thinking scratchpad | N/A | does compute help? |

Code change: raised memo truncation from 120/160 chars to 350 chars, reasoning storage from 150 to 800 chars.

### Results

| Arm | Wins | Rate | Cost | Time | Won quests |
|---|---|---|---|---|---|
| **exp3 baseline: stateful_compact (20w memo)** | **6/36** | **16.7%** | **$3.27** | **65m** | **Pilot x2, Disk, Election, Sortirovka1 x2** |
| compaction_no_memo (ablation) | 2/36 | 5.6% | $2.23 | 68m | Pizza, Disk |
| memo_extended (50w generic) | 2/36 | 5.6% | $4.28 | 89m | Pilot, Election |
| memo_structured (50w format) | 1/36 | 2.8% | $3.91 | 82m | Pizza |
| memo_cot (100w thinking) | 1/36 | 2.8% | $3.15 | 83m | Election |

### Findings

1. **Original 20-word stateful_compact remains the clear winner.** None of the exp4 variations improved on it.
2. **Compaction alone = no memo.** compaction_no_memo matched full_transcript baseline exactly (5.6%), confirming memo is the active ingredient.
3. **More space doesn't help.** memo_extended (50w) = 5.6%, same as no-memo baselines. The bottleneck isn't memo size.
4. **Structure hurts.** Rigid format instructions constrained the model instead of helping it (2.8%).
5. **More compute doesn't help.** 100-word thinking scratchpad performed worst despite most output tokens (2.8%).
6. **Conciseness wins.** The 20-word constraint forced maximally selective state tracking - the right pressure.

### Conclusion

The memo improvement curve is not monotonic: 0 words (5.6%) -> 20 words (16.7%) -> 50 words (5.6%) -> 50 words structured (2.8%). The sweet spot is a short, unconstrained memo. Next improvements should target agent architecture (planner, tools) or knowledge injection, not memo format.

## Exp 5: Baseline Variance (2026-04-28)

**Config**: `configs/benchmarks/exp5_stateful_compact_variance.yaml`
**Model**: Gemini 3 Flash Preview (via OpenRouter)
**Quests**: 18 quests, 5 runs each (90 total)

### Results

Overall: **9/90 (10.0%)**

| Quest | Wins | Type |
|---|---|---|
| Election | 3/5 | Coalition strategy |
| Leonardo | 2/5 | Resource management |
| Disk | 2/5 | Riddle (RNG-dependent) |
| Pilot | 1/5 | Exam with arithmetic |
| Robots | 1/5 | Combat with counters |
| 13 other quests | 0/5 each | Various |

### Findings

- The exp3 result (16.7%) was partially lucky. At 5 runs the rate drops to 10.0%.
- No quest is reliably won: best is Election at 3/5 (60%).
- Quests that never win are consistently zero across all 5 runs.
- Sortirovka1 (won 2/2 in exp3) dropped to 0/5, suggesting its exp3 wins were lucky.

### Failure taxonomy (81 failed traces)

1. **No numeric reasoning** (Pizza, Pilot, Banket): directional heuristics instead of exact computation
2. **No spatial state** (Codebox, Shashki, Player): can't maintain board representation in memo
3. **No trajectory awareness** (Badday, Ski): doesn't notice losing trends
4. **No objective persistence** (Badday, Depth): forgets interactive elements once out of view
5. **Pure RNG** (Disk, Election): stochastic quest branches

## Exp 6: Prompt Hints + Tools (2026-04-29)

**Branch**: `exp6-unified-tools` (PR #27, merged)
**Model**: Gemini 3 Flash Preview (via OpenRouter)
**Quests**: 18 quests, 3 runs each (54 per variant, 162 total)

### Design

Three variants testing prompt content changes and tool augmentation:

| Variant | Template | Description |
|---|---|---|
| C: Prompt hints | stateful_compact_hints.jinja | Baseline 20w memo + "morally grey solutions" + "write exact numbers" hints |
| D: Tools | tool_augmented.jinja | Calculator + scratchpad + quest_history (two-phase: select tools -> execute -> choose) |
| C+D: Tools+hints | tool_augmented_hints.jinja | Tools + both prompt hints combined |

Tools available (always-on, not quest-specific):
- `calculator(expression)`: AST-based arithmetic evaluation
- `scratchpad(operation, content)`: persistent read/write_replace note (max 1200 chars)
- `quest_history(query)`: keyword search over prior observations and actions

### Results

| Variant | Wins | Rate | vs Exp5 (10.0%) |
|---|---|---|---|
| C: Prompt hints | 0/54 | 0.0% | Much worse |
| D: Tools | 3/54 | 5.6% | Worse |
| **C+D: Tools+hints** | **7/54** | **13.0%** | **Better** |

Per-quest breakdown:

| Quest | Hints | Tools | T+H | Exp5 baseline |
|---|---|---|---|---|
| Election | 0/3 | 2/3 | **3/3** | 3/5 |
| Pilot | 0/3 | 0/3 | **2/3** | 1/5 |
| Leonardo | 0/3 | 0/3 | 1/3 | 2/5 |
| Disk | 0/3 | 1/3 | 1/3 | 2/5 |
| All others | 0/3 | 0/3 | 0/3 | 0/5 |

### Findings

1. **Prompt hints alone are harmful (0/54).** Adding "morally grey" and "write exact numbers" guidelines to the baseline template destroyed all wins. The extra instruction text likely interfered with the tight 20-word memo constraint.
2. **Tools alone are modest (5.6%).** Calculator and scratchpad don't help without the prompt hints guiding their use.
3. **The combination is synergistic (13.0%).** Neither component works alone, but together they beat the baseline. The hints tell the model what to track; the tools give it the means.
4. **Election becomes reliably winnable (3/3).** First quest in the project with 100% success. The scratchpad tracks voter support percentages; calculator computes vote totals.
5. **Pilot improves (2/3 vs 1/5).** Calculator helps with theory exam arithmetic.
6. **Pizza remains at 0%.** The "morally grey" hint did not recover the bribery decision - the model still refuses to bribe judges across all variants.

### Conclusion

Tools + prompt hints is the new best architecture at 13.0%, beating the memo-only baseline (10.0%). The improvement comes from Election (now reliable) and Pilot (now consistent). The synergy effect is the key insight: instructions about what to notice + tools to act on it > either alone.

## Exp 7: Multi-Model Comparison (2026-04-29)

**Branch**: `exp4-memo-variations` (master)
**Models**: 5 models via OpenRouter + Anthropic API
**Quests**: 5 winnable quests (Election, Pilot, Leonardo, Disk, Robots), 3 runs each
**Architecture**: stateful_compact (20w memo, compaction interval 50) - same as exp5 baseline

### Design

Test whether the architecture findings from exp3-6 (all using Gemini 3 Flash) generalize across model families. Same prompt template, same hyperparameters, different models.

| Model | Provider | Input $/M | Output $/M |
|---|---|---|---|
| Llama 4 Scout | OpenRouter | $0.08 | $0.30 |
| Claude 3.5 Haiku | Anthropic API | $1.00 | $5.00 |
| DeepSeek V3 0324 | OpenRouter | $0.20 | $0.77 |
| Mistral Small 4 (2603) | OpenRouter | $0.15 | $0.60 |
| Qwen3 30B A3B | OpenRouter | $0.08 | $0.28 |

### Results

| Quest | Llama 4 Scout | Claude Haiku | DeepSeek V3 | Mistral Small 4 | Qwen3 30B | Gemini Flash (exp5) |
|---|---|---|---|---|---|---|
| Election | 2/3 | 0/3 | 1/3 | 0/3 | 0/3 (3 timeouts) | 3/5 |
| Pilot | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 | 1/5 |
| Leonardo | 0/3 | 0/3 | 0/3 | 0/3 | 0/3 (1 timeout) | 2/5 |
| Disk | 2/3 | 2/3 | 0/3 | 1/3 | 1/3 | 2/5 |
| Robots | 0/3 | 1/3 | 0/3 | 0/3 | 0/3 | 1/5 |
| **Total** | **4/15 (27%)** | **3/15 (20%)** | **1/15 (7%)** | **1/15 (7%)** | **1/15 (7%)** | **9/25 (36%)** |

### Findings

1. **Gemini Flash remains the best model for this task at 36% on winnable quests.** No other model matched it despite using the same architecture.
2. **Llama 4 Scout is the strongest alternative at 27%.** Strong on Election (2/3) and Disk (2/3), zero on Pilot/Leonardo/Robots.
3. **Claude Haiku is solid at 20%.** Only model besides Gemini to win Robots (1/3). Strong on Disk (2/3) but zero on Election - opposite pattern from Llama.
4. **DeepSeek V3 and Mistral Small 4 tied at 7%.** Each won only 1 quest run.
5. **Qwen3 30B struggled (7%).** 4 timeouts (3 Election, 1 Leonardo) at 600s suggest the model generates very long outputs or gets stuck in loops.
6. **No model won Pilot or Leonardo.** Gemini's wins on these quests don't transfer - they may depend on Gemini-specific reasoning patterns.
7. **Disk is the most model-independent quest** - won by 5 of 6 models. Its success likely depends on RNG (riddle variant) more than model capability.
8. **Election success varies widely by model** - from 0/3 (Haiku, Mistral, Qwen) to 3/5 (Gemini). Coalition-building strategy appears model-dependent.

### Conclusion

Architecture matters more than model choice for this benchmark, but model choice still matters significantly. The 20w memo + compaction architecture produces non-zero results across all tested models, but the success rate ranges from 7% to 36%. The cheapest models (Qwen, Llama at $0.08/M input) bracket the range: Llama near the top, Qwen near the bottom. Cost does not predict performance here.

## Exp 7b: Model Upgrades (2026-04-30)

**Branch**: `exp7b-model-upgrades` (PR #29)
**Models**: 3 upgraded models replacing the weakest exp7 performers
**Quests**: All 18 quests, 2 runs each (36 per model, 108 total)
**Architecture**: stateful_compact (20w memo, compaction interval 50) - same as exp5/exp7

### Design

Exp7 bottom performers (DeepSeek V3, Qwen3 30B, Mistral Small) scored 7% each. We replaced them with newer versions to test whether model upgrades improve results. Also upgraded Haiku from 3.5 to 4.5.

| Model | Replaces | Provider |
|---|---|---|
| DeepSeek V4 Flash | DeepSeek V3 0324 | OpenRouter |
| Qwen 3.6 Flash | Qwen3 30B A3B | OpenRouter |
| Claude Haiku 4.5 | Claude 3.5 Haiku | Claude CLI (-p mode) |

### Results

| Quest | DeepSeek V4 Flash | Qwen 3.6 Flash | Haiku 4.5 |
|---|---|---|---|
| Badday | 0/2 | 0/2 | 0/2 |
| Pizza | 0/2 | 0/2 | 0/2 |
| Pilot | 0/2 | 0/2 | 0/2 |
| Ski | 0/2 | 0/2 | 0/2 |
| Leonardo | 0/2 | 0/2 | 0/2 |
| Robots | 0/2 | 0/2 | 0/2 |
| Banket | 0/2 | 0/2 | 0/2 |
| Codebox | 0/2 | 0/2 | 0/2 |
| Depth | 0/2 | 0/2 | 0/2 |
| Disk | 0/2 | **2/2** | 0/2 |
| Driver | 0/2 | 0/2 | 0/2 |
| Edelweiss | 0/2 | 0/2 | 0/2 |
| Election | 0/2 | 0/2 | 0/2 |
| Foncers | 0/2 | 0/2 | 0/2 |
| Ministry | 0/2 | 0/2 | 0/2 |
| Player | 0/2 | 0/2 | 0/2 |
| Shashki | 0/2 | 0/2 | 0/2 |
| Sortirovka1 | 0/2 | 0/2 | 0/2 |
| **Total** | **0/36 (0%)** | **2/36 (5.6%)** | **0/36 (0%)** |
| Timeouts | 5 (14%) | 17 (47%) | 19 (53%) |

### Findings

1. **All three upgrades performed worse than their predecessors.** DeepSeek V4 Flash (0%) < V3 (7%), Haiku 4.5 (0%) < 3.5 (20%), Qwen 3.6 Flash (5.6%) < 3 30B (7%).
2. **DeepSeek V4 Flash scored 0/36 with 5 timeouts.** Complete failure across all 18 quests. Worse than V3 which managed 1/15 on the easier subset.
3. **Qwen 3.6 Flash had a 47% timeout rate** (17/36), suggesting the model generates excessively long outputs. Only won Disk (2/2), which is RNG-dependent.
4. **Haiku 4.5 scored 0/36 with 53% timeout rate** (19/36). The Claude CLI `-p` mode added ~7s latency per step, contributing to timeouts. Failed even on Disk, which 5 of 6 exp7 models won.
5. **Newer model versions do not automatically improve on this benchmark.** The task rewards concise, focused responses. Models optimized for longer reasoning chains may perform worse when the memo constraint demands brevity.
6. **Timeout rates correlate inversely with success.** Gemini Flash (exp5 baseline, ~0% timeouts) >> Qwen 3.6 (47% timeouts) >> Haiku 4.5 (53% timeouts). Models that run long on a single step waste budget better spent on more turns.

### Conclusion

Model upgrades hurt rather than helped. The benchmark penalizes verbosity: models that generate longer outputs hit the 600s quest timeout before reaching completion, especially on longer quests. The exp7 ranking stands: Gemini Flash > Llama 4 Scout > Claude Haiku 3.5 > DeepSeek V3 = Mistral Small = Qwen3 30B. Flash/distilled models optimized for speed and conciseness outperform larger or newer variants on this task.
