# Preliminary paper and tiered benchmark rollout implementation plan

Goal: turn the current repo state into an honest preliminary benchmark writeup, anchored on an easy -> medium -> hard benchmark progression and the new canonical model lineup.

Architecture: keep the paper/blog post tightly coupled to committed artifacts. Treat the current site as a preliminary paper, derive empirical claims only from committed benchmark outputs, then extend the dataset with tiered benchmark runs and regenerate leaderboard/report artifacts after each tier. Do not describe planned final-study scope as if it already exists.

Tech stack: Python CLI via uv, existing llm-quest benchmark runner, site/leaderboard.json, benchmark artifacts under results/benchmarks, and a repository-local paper directory for the arXiv draft.

## Ground truth decisions locked

- Target machine: this Ubuntu VPS.
- Target repo: `/root/llm_quest_benchmark`.
- Canonical paper framing: honest preliminary benchmark draft.
- Canonical public result source: the six-model published leaderboard slice in `site/leaderboard.json`.
- Analysis order: easy benchmark first, then medium, then hard.
- Tier configs under `configs/benchmarks/tiered/` define the next balanced rerun matrix. They are planning artifacts until reruns are executed.

## Phase 0: normalize repo state before writing

1. Inventory current benchmark artifacts and separate published evidence from exploratory local archives.
2. Freeze the empirical easy, medium, and hard quest packs already proposed in the tiered configs.
3. Ensure the paper cites only numbers that can be traced to committed data or explicitly marked local exploratory artifacts.

## Phase 1: write from committed evidence

1. Extract tier summaries, quest summaries, and mode/model rollups from `site/leaderboard.json`.
2. Build a paper-facing data bundle under `paper/data/` plus generated table fragments under `paper/tables/`.
3. Draft the preprint around three claims:
   - the difficulty cliff from easy to medium to hard is already obvious;
   - the current public archive is coverage-uneven across modes and should be read descriptively;
   - the next balanced rerun should use the tiered configs on the current six-model lineup.

## Phase 2: define the missing reruns and ablations

Balanced rerun plan, but do not execute it in this change:

1. A-D balanced matrix on the current six-model lineup:
   - 15 quests x 6 models x 4 modes x 3 runs.
2. Targeted tool-mode follow-up:
   - easy and medium tiers plus `Election_eng`, where hard-tier nonzero signal already exists.
3. Stability rerun:
   - repeat the best and worst cells with additional independent runs.
4. Human baseline:
   - collect small-scale play traces through `site/play.html`.

## Phase 3: publication hygiene

1. Keep the site coherent with `master`: do not restore the deleted `site/paper.html`.
2. Move paper work into `paper/` rather than reviving stale HTML drafts.
3. Explain in the PR that no new expensive benchmark matrices were run.
