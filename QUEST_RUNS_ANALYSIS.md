# Quest Runs Analysis

## Scope
This document analyzes existing run artifacts only (no new quest executions).

Primary data sources:
- `/Users/conscience/Workspace/llm_quest_benchmark/results/llm_*/**/run_*/run_summary.json`
- `/Users/conscience/Workspace/llm_quest_benchmark/results/benchmarks/report_provider_matrix.md`
- Runtime bridge code:
  - `/Users/conscience/Workspace/llm_quest_benchmark/llm_quest_benchmark/executors/ts_bridge/bridge.py`
  - `/Users/conscience/Workspace/llm_quest_benchmark/llm_quest_benchmark/executors/ts_bridge/consoleplayer.ts`
  - `/Users/conscience/Workspace/llm_quest_benchmark/space-rangers-quest/src/lib/qmplayer/funcs.ts`

## Corpus Snapshot
- Total run summaries: `197`
- Outcomes:
  - `24` success
  - `171` failure
  - `2` error
- Quest-level success:
  - `Diehard`: `10/11` (90.9%)
  - `Boat`: `14/27` (51.9%)
  - `Examen`: `0/55`
  - `Banket_eng`: `0/28`
  - `Fishing`: `0/26`
  - `Rush`: `0/25`
  - `Gobsaur`: `0/25`

Key observation: except simple/control quests (`Diehard`, partially `Boat`), all target benchmark quests are consistently failing.

## Focused Benchmark Runs
Recent matrix benchmarks:
- `CLI_benchmark_20260214_235403` (baseline reasoning): `2/24` success
- `CLI_benchmark_20260215_000103` (consequence prompt): `2/24` success (`1` timeout)
- `CLI_benchmark_20260215_000925` (objective/system variant): `2/24` success
- `CLI_benchmark_20260215_002034` (provider-tuned v1): `3/24` success

So prompt variants shift which provider wins `Boat`, but do not break through on `Examen/Fishing/Gobsaur/Rush/Banket_eng`.

## High-Confidence Root Causes

### 1) Important game state is not exposed to the agent
Evidence:
- TS engine `PlayerState` contains `paramsState`:
  - `/Users/conscience/Workspace/llm_quest_benchmark/space-rangers-quest/src/lib/qmplayer/funcs.ts:263`
- Python bridge currently discards it and forwards only `text + choices`:
  - `/Users/conscience/Workspace/llm_quest_benchmark/llm_quest_benchmark/executors/ts_bridge/bridge.py:242`
  - `/Users/conscience/Workspace/llm_quest_benchmark/llm_quest_benchmark/executors/ts_bridge/bridge.py:294`

Impact hypothesis:
- Quests like `Examen` likely depend on hidden/current parameters (stats, checks, progression counters).
- Agent decides with incomplete state, so "reasonable" choices can still be systematically wrong.

### 2) Bridge fallback creates synthetic terminal failures
Evidence:
- `51/197` runs end with `final_state.location_id == "0"` and marker:
  - `"[Game progressed to next state]"`
- All such runs are failures (`51/51`).
- Concentrated in exactly the hard quests:
  - `Fishing`: `17`
  - `Rush`: `17`
  - `Banket_eng`: `17`
- Fallback logic synthesizes `state` with empty choices and `gameState=complete` when `'state'` key is missing:
  - `/Users/conscience/Workspace/llm_quest_benchmark/llm_quest_benchmark/executors/ts_bridge/bridge.py:406`

Impact hypothesis:
- A subset of failures are harness-induced terminal states rather than genuine quest failures.
- This also contaminates benchmark trust for those quests.

Representative artifacts:
- `/Users/conscience/Workspace/llm_quest_benchmark/results/llm_gpt-5-mini/Fishing/run_779/run_summary.json`
- `/Users/conscience/Workspace/llm_quest_benchmark/results/llm_gpt-5-mini/Rush/run_783/run_summary.json`
- `/Users/conscience/Workspace/llm_quest_benchmark/results/llm_gpt-5-mini/Banket_eng/run_787/run_summary.json`

### 3) Policy bias produces homogeneous wrong choices
Evidence patterns from latest runs:
- `Examen`: models consistently choose "help alkaris" branch and die quickly.
- `Fishing`: models consistently choose "agree" (likely right), but still collapse later.
- `Gobsaur`: models consistently choose direct "search disk" near sleeping monster and die.
- `Rush`: models repeatedly choose "maintain speed" and fail.
- `Banket_eng`: first decision explores only subset of options (`2/3/4`), never tries (`1/5/6`) in sampled matrix runs.

Impact hypothesis:
- Current prompts over-emphasize "immediate mission progress / info gathering" and underweight tactical survival or non-obvious branch exploration.
- For some quests, best action may be counterintuitive under current prompt priors.

### 4) Single-step greedy policy is too weak for these quests
Observations:
- No lookahead/search/backtracking.
- No explicit uncertainty handling over stochastic transitions.
- No branch testing at critical forks.

Impact hypothesis:
- Many quests appear to require multi-step planning with hidden variable sensitivity.
- A strict one-step argmax policy will systematically miss long-horizon successful paths.

## Quest-by-Quest Failure Notes

### Examen
- Runs: `55`, success: `0`
- Frequent terminal narratives:
  - street-fight failure after "help alkaris"
  - labor exam failure due physical exhaustion
- Key issue: model cannot access explicit stat panel (`paramsState` missing), but decisions seem stat-sensitive.

Representative failures:
- `/Users/conscience/Workspace/llm_quest_benchmark/results/llm_gpt-5-mini/Examen/run_785/run_summary.json`
- `/Users/conscience/Workspace/llm_quest_benchmark/results/llm_claude-sonnet-4-5/Examen/run_797/run_summary.json`
- `/Users/conscience/Workspace/llm_quest_benchmark/results/llm_gemini-2.5-flash/Examen/run_809/run_summary.json`
- `/Users/conscience/Workspace/llm_quest_benchmark/results/llm_deepseek-3.2-chat/Examen/run_821/run_summary.json`

### Fishing
- Runs: `26`, success: `0`
- Typical path: agree mission -> bait loop -> synthetic bridge terminal failure in many runs.
- Marker-induced fallback is very common (`17` runs).

Representative failures:
- `/Users/conscience/Workspace/llm_quest_benchmark/results/llm_gpt-5-mini/Fishing/run_779/run_summary.json`
- `/Users/conscience/Workspace/llm_quest_benchmark/results/llm_gemini-2.5-flash/Fishing/run_803/run_summary.json`

### Gobsaur
- Runs: `25`, success: `0`
- Typical model choice: direct disk search near active threat.
- Suggests poor risk modeling under monster-threat context.

Representative failures:
- `/Users/conscience/Workspace/llm_quest_benchmark/results/llm_gpt-5-mini/Gobsaur/run_781/run_summary.json`
- `/Users/conscience/Workspace/llm_quest_benchmark/results/llm_deepseek-3.2-chat/Gobsaur/run_817/run_summary.json`

### Rush
- Runs: `25`, success: `0`
- Repeated "maintain speed" behavior and no successful long-run policy.
- Also has frequent synthetic terminal fallback (`17` runs).

Representative failures:
- `/Users/conscience/Workspace/llm_quest_benchmark/results/llm_gpt-5-mini/Rush/run_783/run_summary.json`
- `/Users/conscience/Workspace/llm_quest_benchmark/results/llm_gemini-2.5-flash/Rush/run_807/run_summary.json`

### Banket_eng
- Runs: `28`, success: `0`
- Mostly fails at/near first decision region.
- Fallback marker appears in many runs (`17`).
- Option exploration is narrow in sampled benchmarks.

Representative failures:
- `/Users/conscience/Workspace/llm_quest_benchmark/results/llm_gpt-5-mini/Banket_eng/run_787/run_summary.json`
- `/Users/conscience/Workspace/llm_quest_benchmark/results/llm_claude-sonnet-4-5/Banket_eng/run_799/run_summary.json`

### Boat
- Runs: `27`, success: `14`
- Confirms pipeline can work end-to-end for structured logic puzzle quests.
- This is a useful sanity check but not representative of harder quest dynamics.

Representative success:
- `/Users/conscience/Workspace/llm_quest_benchmark/results/llm_gemini-2.5-flash/Boat/run_801/run_summary.json`

## Prioritized Improvement Plan (Harness + Agent)

### Priority A: Fix harness reliability before more prompt tuning
1. Bridge should preserve and expose `paramsState` (and optionally raw param values where available) to the agent.
2. Replace synthetic terminal fallback strategy:
   - on missing `'state'`, try explicit `get_state` recovery first
   - persist raw bridge stderr/stdout fragment into run summary for diagnosis
   - tag synthetic termination explicitly (`synthetic_end=true`) instead of blending with normal failures
3. Keep benchmark outcome canonical and provenance-rich:
   - include `end_reason` (`quest_success`, `quest_failure`, `timeout`, `bridge_synthetic`, `exception`)

### Priority B: Improve decision policy at critical forks
1. Add branch search at multi-choice steps (at least depth-1 rollout on each candidate).
2. Add anti-homogeneity mechanism:
   - when confidence low, diversify from repeated historical failure choices.
3. Split policy objectives:
   - survival/risk management
   - mission progression
   - hidden-state info acquisition

### Priority C: Focus model iteration on Gemini 2.5 Flash
Rationale:
- Stable API behavior, low cost, and competitive outcomes in current set.
- Good candidate for rapid iteration.

Suggested loop:
1. Fix bridge + state exposure.
2. Run only Gemini on the 6-quest set.
3. Inspect run summaries for changed failure topology.
4. Only then broaden provider matrix again.

## Open Questions for External Oracle
1. Given these artifacts, what is the best minimal state representation for LLM control in QM quests (`text`, `paramsState`, counters, history)?
2. Is one-step prompting fundamentally insufficient here, and what planning architecture gives best cost/performance tradeoff?
3. How should we detect and quarantine harness-induced terminal failures so benchmark metrics stay trustworthy?
4. For `Examen/Rush/Fishing`, what strategy class should dominate: risk-averse, exploratory, or parameter-inference-first?

## Supplemental Artifacts
- Combined benchmark comparison:
  - `/Users/conscience/Workspace/llm_quest_benchmark/results/benchmarks/report_provider_matrix.md`
- Main analysis command target:
  - all `run_summary.json` under `/Users/conscience/Workspace/llm_quest_benchmark/results/`
