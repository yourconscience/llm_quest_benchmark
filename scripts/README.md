# Scripts

Utility/debug scripts that are kept in sync with current web/CLI workflow.

- `debug_database.py`: inspect `metrics.db` and `instance/llm_quest.sqlite`, plus a quick benchmark write-check.
- `inspect_app.py`: print Flask routes and runtime hints.
- `debug_template.py`: parse benchmark analysis template for syntax errors.
- `test_benchmark_load.py`: load latest benchmark rows from web DB.
- `test_template_rendering.py`: render benchmark analysis template with current DB data.

Notes:
- Run scripts from repo root (`uv run python scripts/<name>.py`).
- These are diagnostics/helpers, not part of pytest.
