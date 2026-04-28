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

### Results

_Pending re-run with timeout fix._
