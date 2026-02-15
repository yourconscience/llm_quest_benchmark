# Quest Runs Analysis (Post-Bridge-Fix)

## Scope
This document summarizes run artifacts after the recent bridge fixes (stdout-noise handling + `params_state` exposure) and two full Gemini benchmark sweeps.

Primary artifacts used:
- `results/benchmarks/CLI_benchmark_20260215_232520/benchmark_summary.json`
- `results/benchmarks/CLI_benchmark_20260216_000923/benchmark_summary.json`
- Representative run summaries:
  - `results/llm_gemini-2.5-flash/Rush/run_1189/run_summary.json`
  - `results/llm_gemini-2.5-flash/Banket_eng/run_1025/run_summary.json`
  - `results/llm_gemini-2.5-flash/Prison1/run_1187/run_summary.json`
  - `results/llm_gemini-2.5-flash/Examen/run_1161/run_summary.json`

## Benchmarks Executed

### 1) SR 2.1.2121 ENG (all quests)
- Benchmark ID: `CLI_benchmark_20260215_232520`
- Config: `configs/benchmarks/gemini_sr_2_1_2121_eng_all.yaml`
- Quests: `35`
- Model: `gemini-2.5-flash`, `reasoning.jinja`, `temperature=0.4`, `timeout=60s`
- Result:
  - Success: `0`
  - Failure: `6`
  - Timeout: `29`
  - Error: `0`

### 2) KR 1 RU (all quests)
- Benchmark ID: `CLI_benchmark_20260216_000923`
- Config: `configs/benchmarks/gemini_kr_1_ru_all.yaml`
- Quests: `26`
- Model: `gemini-2.5-flash`, `reasoning.jinja`, `temperature=0.4`, `timeout=60s`
- Result:
  - Success: `0`
  - Failure: `14`
  - Timeout: `12`
  - Error: `0`

## What Improved (Harness Quality)

### 1) Bridge corruption symptoms are gone in sampled post-fix runs
Previously common synthetic terminal marker (`[Game progressed to next state]`) is not present in representative post-fix runs.

### 2) Status panel is now visible to the agent
`params_state` is present in run summaries and included in observations (`Status:` block), including stat-like quests (e.g. `Rush`, `Examen`).

### 3) Timeout/outcome consistency is improved
Timeouts are now recorded as `TIMEOUT` rather than being overwritten by late runner writes.

## Current Failure Topology

### 1) Very high timeout pressure in long quests
- ENG set: `29/35` timeouts.
- RU set: `12/26` timeouts.

60 seconds is likely too short for many quests given per-step LLM latency.

### 2) Policy loops still dominate some quests
Example: `Rush` (`run_1189`) ends via loop guard with forced terminalization metadata:
- `info.forced_completion=true`
- `info.reason="infinite_loop_detected"`
- Repetitive driving-choice regime without objective progress.

### 3) Decision quality is often low-information
Many Gemini `llm_decision.reasoning` entries are just compact raw outputs (`raw_response: 1` / `raw_response: 2`) instead of structured analysis/reasoning. This indicates the model often follows numeric-only response style without preserving actionable rationale.

### 4) Provider response edge case observed
During `Prison1` run, logs showed retries failing with:
- `'NoneType' object has no attribute 'content'`

This indicates some provider responses may contain `choices[0].message == None`.

## New Fixes Added in This Branch After These Runs
1. `OpenAICompatibleClient` now safely handles missing message content (`message=None`) instead of raising.
2. LLM error fallback now stores explicit reasoning marker (`llm_call_error: ...`) instead of blank reasoning.
3. Timeout outcome recording now carries `benchmark_id`, improving post-hoc benchmark/run correlation for timeout runs.

Note: historical run summaries created before this fix can still miss `benchmark_id` on timeout rows.

## Root-Cause Hypotheses (Current)

1. **Budget mismatch**: 60s timeout is not aligned with real quest length + API latency.
2. **Greedy local policy**: one-step numeric selection struggles on branching quests with delayed consequences.
3. **Weak anti-loop control**: no explicit mechanism to avoid repeating state/action cycles.
4. **Prompt under-specification for objective tracking**: model sees state + choices but does not maintain a robust long-horizon objective/value model.

## Recommended V2 Experiment Plan (Gemini-focused)

1. Increase timeout to `180s` for full-quest benchmarks.
2. Add explicit anti-loop policy in agent:
   - detect repeated `(location_id, params_state, chosen_action)` patterns;
   - penalize repeated action in same repeated state.
3. Strengthen prompt contract for planning:
   - require concise per-choice consequence estimate before selecting;
   - include explicit objective reminder each step;
   - keep strict final action schema.
4. Add a cheap search policy at forks:
   - depth-1 rollout with save/load (or deterministic replay where possible).
5. Keep Gemini as primary iteration target until success > 0 on non-trivial quests.

## Suggested Near-Term Success Criterion
For the next run set (same quest groups, timeout 180):
- At least one non-trivial quest (`Examen`, `Fishing`, `Rush`, `Banket_eng`, `Gobsaur`) reaches `SUCCESS`.
- Timeout share reduced by at least 30% relative to current baseline.
