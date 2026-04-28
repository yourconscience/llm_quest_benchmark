# Experiments Log

Record of benchmark experiments, findings, and decisions. Keeps history out of source code.

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

## Next Plan: Baseline Replication + Unified Tools

### Decisions

- Exp 5 is a pure replication of the current best architecture: `stateful_compact` with a 20-word memo, compaction mode, same 18-quest set, same Gemini 3 Flash Preview model, 5 runs per quest.
- Do not add a 30-word memo arm to Exp 5. That would mix replication with prompt tuning and make variance harder to interpret.
- Tools must be evaluated as an always-enabled architecture on the full quest set, not selectively enabled by quest. The benchmark should test a general agent mode, not quest-specific routing.
- First unified-tools run should be cheap: 2 runs per quest across the same 18 quests. Scale only if it does not clearly hurt relative to the Exp 5 baseline.
- Planner experiments are postponed until tool/planner memory propagation is fixed and verified.

### Required fix before planner or tool experiments

`PlannerAgent` and `ToolAgent` inherit from `LLMAgent`, but current factory and prompt construction do not give them the same memory surface as the winning baseline.

Known issue:

- `agent_factory.create_agent()` passes `memory_mode` and `compaction_interval` only to plain `LLMAgent`.
- `PlannerAgent` and `ToolAgent` build prompts from raw `state`, while plain `LLMAgent` uses `_build_contextual_state(state)` to inject the quest briefing, full transcript, compaction summary, recent steps, and memo history.

Fix requirement:

- Pass `memory_mode` and `compaction_interval` into `PlannerAgent` and `ToolAgent`.
- Ensure planner/tool prompts receive the same contextual state block as the baseline when `memory_mode` is `full_transcript` or `compaction`.
- Add focused tests proving `create_agent(..., action_template="tool_augmented", memory_mode="compaction")` and planner equivalent preserve that setting and include contextual memory in prompts.

### Exp 5: Baseline variance

Goal: measure variance of the current best architecture.

Config:

- Model: `openrouter:google/gemini-3-flash-preview`
- Template: `stateful_compact`
- Memory mode: `compaction`
- Compaction interval: `50`
- Runs: `5`
- Quests: same 18 quests from Exp 3 / Exp 4

Primary readout:

- Overall success rate and Wilson interval.
- Per-quest wins out of 5.
- Cost and wall-clock time.
- Whether previously solved quests remain solved: `Pilot`, `Disk`, `Election`, `Sortirovka1`.

Decision after Exp 5:

- If the 20-word baseline collapses under 5 runs per quest, prioritize variance analysis before new architecture claims.
- If it remains meaningfully above no-memo/full-transcript baselines, use it as the control for Exp 6.

### Exp 6: Unified tools screen

Goal: test whether a general always-on tool architecture improves quest completion without quest-specific routing.

Implementation status (2026-04-28):

- Branch: `exp6-unified-tools`
- Memory propagation fix implemented for `PlannerAgent` and `ToolAgent`.
- Tool metadata is exported in `run_summary.json` under `llm_decision.tool_calls` and `llm_decision.tool_results`.
- Unified tools implemented: `calculator`, `scratchpad`, and existing `quest_history`.
- Screening config added: `configs/benchmarks/exp6_unified_tools_screen.yaml`.
- Smoke run on `Banket_eng` and `Shashki_eng` completed 0/2. This verifies plumbing and logging, but suggests the first tool prompt may overuse scratchpad on board-state quests and loop on drink-mixing arithmetic. Treat the full 18-quest screen as exploratory, not as a likely winner until Exp 5 variance is known.

Architecture:

- Base memory architecture: same as Exp 5 (`stateful_compact`, compaction, 20-word memo behavior).
- Agent mode: tool-augmented.
- Tools available on every quest:
  - `calculator(expression)`: deterministic arithmetic for totals, deltas, percentages, linear constraints, and simple comparisons.
  - `scratchpad(operation, content)`: one persistent run-local free-form note blob for board states, coordinates, inventories, discovered rules, failed branches, and candidate plans.
  - `quest_history(query)`: existing run-local search over prior observations and selected actions.

Tool constraints:

- No quest-name-specific tools.
- No hardcoded solvers for `Codebox`, `Shashki`, `Depth`, or any other quest.
- Tools may be useful for board and spatial quests only through generic arithmetic, scratchpad state tracking, and history lookup.
- Scratchpad API stays minimal: `read` returns the current note; `write_replace` replaces it with a concise updated note. No append mode initially.
- Tool use is optional per decision, but the tool-capable architecture is always enabled for all 18 quests.
- Keep max tool calls small, initially 1 per selection pass unless there is a concrete reason to allow 2.

Screening config:

- Model: `openrouter:google/gemini-3-flash-preview`
- Quests: same 18 quests as Exp 5
- Runs: `2`
- Memory mode: `compaction`
- Compaction interval: `50`

Primary readout:

- Overall success rate vs Exp 5 per-quest rates.
- Tool-call frequency per quest.
- Parse/default rate.
- Token and cost overhead.
- Quests where tools appear to hurt previously stable wins.

Scale-up rule:

- Run a 5-run version only if the 2-run screen is not obviously worse on success rate, parse rate, and cost.

### Later work

- Test planner only after memory propagation is fixed and the unified-tools screen is understood.
- After identifying a winning architecture, rerun across multiple models.
- Expand quest set and consider Russian versions only after the architecture question is clearer.
- Remove or mark impossible/pathological quests based on empirical evidence, not before the core architecture comparison is stable.
