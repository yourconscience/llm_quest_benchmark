# Gemini SR2 EN A/B: Baseline vs Subgoal+Risk

Date: 2026-02-16

## Goal
Evaluate whether adding:
- subgoal memory block (via `consequence_scan_subgoal.jinja`)
- a one-line risk reminder in system prompt (`system_role_risk.jinja`)

improves success rate vs baseline Gemini prompting on the large SR2 EN quest set.

## Setup
- Quest set: `quests/sr_2_1_2121_eng` (directory benchmark)
- Model: `gemini-2.5-flash`
- Timeout: `180s`
- Agents:
  - Baseline: `system_role.jinja` + `consequence_scan.jinja`
  - Improved: `system_role_risk.jinja` + `consequence_scan_subgoal.jinja`

Benchmark IDs:
- Baseline: `CLI_benchmark_20260216_225801_a9110419`
- Improved: `CLI_benchmark_20260216_225802_d0af4029`

## Result (matched comparable slice)
The improved run stalled later in the matrix, so comparison is made on the **first 16 quests completed by both runs**.

- Baseline success: **9 / 16 (56.25%)**
- Improved success: **7 / 16 (43.75%)**

Per-quest outcomes (baseline vs improved):
- `Badday_eng`: SUCCESS vs SUCCESS
- `Banket_eng`: SUCCESS vs FAILURE
- `Borzukhan_eng`: FAILURE vs FAILURE
- `Codebox_eng`: FAILURE vs FAILURE
- `Depth_eng`: SUCCESS vs SUCCESS
- `Disk_eng`: SUCCESS vs FAILURE
- `Driver_eng`: FAILURE vs FAILURE
- `Edelweiss_eng`: SUCCESS vs SUCCESS
- `Election_eng`: FAILURE vs SUCCESS
- `Elus_eng`: SUCCESS vs FAILURE
- `Evidence_eng`: SUCCESS vs SUCCESS
- `Fishingcup_eng`: SUCCESS vs SUCCESS
- `Foncers_eng`: SUCCESS vs SUCCESS
- `Jumper_eng`: FAILURE vs FAILURE
- `Leonardo_eng`: FAILURE vs FAILURE
- `Logic_eng`: FAILURE vs FAILURE

## Interpretation
- The subgoal+risk variant did **not** outperform baseline on this large-set sample.
- It recovered one quest (`Election_eng`) but lost several (`Banket_eng`, `Disk_eng`, `Elus_eng`).
- Net effect on matched slice: **-2 successes** vs baseline.

## Notes
- Benchmark ID collision issue is fixed (new IDs include random suffix).
- During long runs, occasional provider/client instability was observed (e.g. retries and one `NoneType ... content` failure path in baseline logs), which should be hardened separately.
