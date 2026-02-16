# Scripts

Utility/debug scripts that are kept in sync with current web/CLI workflow.

- `debug_database.py`: inspect `metrics.db` and `instance/llm_quest.sqlite`, plus a quick benchmark write-check.
- `inspect_app.py`: print Flask routes and runtime hints.
- `debug_template.py`: parse benchmark analysis template for syntax errors.
- `test_benchmark_load.py`: load latest benchmark rows from web DB.
- `test_template_rendering.py`: render benchmark analysis template with current DB data.
- `run_provider_matrix.sh`: run baseline + two prompt variants and generate one combined markdown report.
- `doc_gardening.sh`: run the stale-doc scanner used by `skills/doc-gardening`.

Notes:
- Run scripts from repo root (`uv run python scripts/<name>.py`).
- Shell helpers can be run directly (for example `./scripts/doc_gardening.sh`).
- These are diagnostics/helpers, not part of pytest.
