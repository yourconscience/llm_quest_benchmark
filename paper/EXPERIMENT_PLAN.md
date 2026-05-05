# Remaining Experiments and Ablations

These are the missing experiments for a stronger second draft. They are planned only in this branch.

## 1. Balanced A-D tier rerun

Use the current six-model lineup from `site/leaderboard.json` with the committed tier configs:

- Easy: 3 quests
- Medium: 3 quests
- Hard: 9 quests
- Modes: `stub`, `reasoning`, `light_hints`, `planner`
- Runs: 3 per cell

Exact matrix size:

- `15 quests x 6 models x 4 modes x 3 runs = 1080 runs`

This is the main missing experiment because it removes the current coverage imbalance.

## 2. Targeted tool-mode follow-up

Run `tool_augmented` only where the public archive already suggests signal:

- Easy tier: `Boat`, `Badday_eng`, `Pizza_eng`
- Medium tier: `Ski_eng`, `Robots_eng`, `Leonardo_eng`
- Hard candidate: `Election_eng`

Exact matrix size:

- `7 quests x 6 models x 1 mode x 3 runs = 126 runs`

Rationale: tool mode already has sparse nonzero hard-tier evidence, but not enough coverage for a clean claim.

## 3. Repeat-run stability check

For the strongest and weakest observed cells after the balanced rerun:

- add repeated independent runs
- report run counts alongside every success claim
- test whether current easy-tier wins are stable or lucky

## 4. Frontier-model appendix

Keep the main paper on the production-tier six-model lineup. Add a separate appendix run for frontier models only after the balanced rerun is complete.

## 5. Human baseline

Collect small-scale human play traces from `site/play.html`:

- time-to-finish
- win rate on easy and medium tiers
- qualitative comparison against agent failure modes
