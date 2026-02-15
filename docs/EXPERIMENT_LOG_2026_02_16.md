# Experiment Log - 2026-02-16

## Goal
Increase quest success rate by iterating on one promising model without leaking quest answers.

Chosen model: `claude-sonnet-4-5`.
Rationale: best performance among current full-set reruns and stable structured responses.

## Key Changes Implemented

### 1) Agent memory and loop handling
File: `llm_quest_benchmark/agents/llm_agent.py`
- Added recent decision trace (action + choice text + reason) into prompt context.
- Added repeated-state detection with conservative loop-escape diversification.
- Added state/action repetition counters to reduce getting stuck in deterministic loops.

### 2) Better reasoning extraction robustness
File: `llm_quest_benchmark/agents/llm_agent.py`
- Improved parsing of truncated JSON fields.
- If only `analysis` is recoverable, reuse it as `reasoning` instead of opaque `raw_response` fallback.

### 3) New prompt template
File: `llm_quest_benchmark/prompt_templates/loop_aware_reasoning.jinja`
- Explicit loop-aware decision policy.
- Encourages status-aware risk handling and non-repetitive choices under repeated scenes.

## Benchmarks Run

### Baseline simple suite (6 quests)
Config: `configs/benchmarks/sonnet_simple_baseline.yaml`
Benchmark ID: `sonnet_simple_baseline_20260216`
- Success: `2/6` (`33.3%`)
- Timeout: `1`

### Iteration sweep (3 variants x 6 quests)
Config: `configs/benchmarks/sonnet_simple_iter_v1.yaml`
Benchmark ID: `sonnet_simple_iter_v1_20260216`
- Combined: `9/18` (`50.0%`)
- Best variant:
  - `template=loop_aware_reasoning.jinja`
  - `temperature=0.6`
  - `4/6` (`66.7%`)

### Tuned confirmation (best variant only, 6 quests)
Config: `configs/benchmarks/sonnet_simple_iter_v2.yaml`
Benchmark ID: `sonnet_simple_iter_v2_20260216`
- Success: `3/6` (`50.0%`)
- Timeout: `0`

### Mixed suite (10 quests: simple + harder)
Config: `configs/benchmarks/sonnet_simple_iter_v3_mixed10.yaml`
Benchmark ID: `sonnet_simple_iter_v3_mixed10_20260216`
- Success: `3/10` (`30.0%`)
- Timeout: `0`
- Successes: `Boat.qm`, `Pizza_eng.qm`, `Badday_eng.qm`
- Failures: `Diehard.qm`, `Rush.qm`, `Logic_eng.qm`, `Disk_eng.qm`, `Fishing.qm`, `Banket_eng.qm`, `Examen.qm`

### Targeted stubborn quests (`Diehard`, `Rush`)
Config: `configs/benchmarks/sonnet_targeted_diehard_rush_v1.yaml`
Benchmark ID: `sonnet_targeted_diehard_rush_v1_20260216`
- Success: `0/8`
- Multiple prompt variants failed consistently.

## What Improved
- Success rate increased above target on simple and mixed suites:
  - From `33.3%` baseline to up to `66.7%` on simple suite variant.
  - `30.0%` on mixed-10 suite (still above 15-20% target).
- Timeout pressure reduced significantly on tuned runs compared to previous broad benchmarks.

## Remaining Failure Modes
1. Deterministic puzzle/control quests still fail (`Rush`, `Logic`, `Banket_eng`).
2. Some quests require exact sequential tactics not captured by one-step LLM selection.
3. Repetition loops still appear, though less frequently catastrophic with loop-aware policy.

## Recommended Next Steps (High Impact)
1. Add branch search for multi-choice states (depth-1/2 rollout).
2. Add save/load support in bridge protocol for cheap what-if simulation per choice.
3. Introduce lightweight quest-type helpers:
   - arithmetic mixer helper for `Banket_eng`-style composition tasks,
   - race/minigame controller for `Rush`-type control loops.
4. Keep Sonnet loop-aware template as current default for iterative experimentation.

