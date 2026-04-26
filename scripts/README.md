# Scripts

Utility scripts for analysis, data processing, and maintenance.

## Error Analysis Pipeline
- `select_runs_for_analysis.py`: stratified sampling of runs for manual analysis.
- `classify_failures.py`: LLM-judge failure mode classification.
- `build_priority_matrix.py`: priority matrix from classified failures.
- `compute_empirical_difficulty.py`: compute difficulty tiers from metrics.db success rates.
- `replay_runs.py`: replay runs for location trace extraction.

## Data & Maintenance
- `backfill_costs.py`: retroactive cost computation for runs missing cost data.
- `extract_quest_metadata.js`: extract metadata from .qm quest files.
- `update_leaderboard.sh`: generate leaderboard JSON from metrics.db.
- `doc_gardening.sh`: wrapper for doc-gardening skill.

Notes:
- Run Python scripts from repo root: `uv run python scripts/<name>.py`
- Shell scripts can be run directly: `./scripts/<name>.sh`
