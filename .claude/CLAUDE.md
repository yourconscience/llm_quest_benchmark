# LLM Quest Benchmark Development Guide

## Repository Navigation

This repository is organized with clear documentation in the `.claude` directory:

- **Repository Structure**: See `.claude/guides/repo_structure.md`
- **Code Patterns**: Common patterns in `.claude/guides/code_patterns.md`
- **CLI Commands**: Command reference in `.claude/guides/cli_commands.md`

## Core Principles
- **QM First**: Focus on Space Rangers quest experience
- **Developer Experience**: Prioritize testing, logging, and debugging
- **Minimal Dependencies**: Focus on essential tools and libraries
- **Data-Driven Analysis**: Prioritize metrics collection and visualization

## Git Workflow
- Use concise, descriptive commit messages (one line preferred)
- Include appropriate ticket/issue references when applicable
- Group related changes into a single commit when possible

## Common Commands
- Package management: `uv pip install [package]` (ALWAYS use uv instead of pip)
- Install: `./install.sh` or `.\install.ps1`
- Run tests: `pytest` or specific test: `pytest llm_quest_benchmark/tests/test_file.py::TestClass::test_function`
- Type checking: `mypy llm_quest_benchmark`
- Run with LLM: `llm-quest run --quest quests/Boat.qm --model gpt-4o --debug`
- Run benchmark: `llm-quest benchmark --config configs/test_benchmark.yaml`
- Play interactive: `llm-quest play --quest quests/boat.qm --skip`
- Start web interface: `llm-quest server`
- Analyze results: `llm-quest analyze`
- Check code quality: `pre-commit run --all-files`

## Code Style
- Python 3.11+ with type hints required for all public interfaces
- Use absolute imports within the package (from llm_quest_benchmark.module import X)
- Follow PEP 8 guidelines for Python code
- Snake_case for variables and functions, PascalCase for classes
- Handle exceptions with proper logging (use core.logging module)
- Document public functions/classes with docstrings
- All code must pass pre-commit checks
- Lock files (uv.lock) must be committed
- TypeScript: Use linting with `npm run lint` in space-rangers-quest directory

## Project Structure
- Core logic in `llm_quest_benchmark/`
- Tests in `llm_quest_benchmark/tests/`
- Quest files in `quests/`
- Agent configurations in `agents/`
- Web UI templates in `llm_quest_benchmark/web/templates/`
- QM parser in `space-rangers-quest/src/lib/qmreader.ts`

## Agent Features

### Memory System
- **Types**: `message_history` (raw history) and `summary` (LLM-generated summaries)
- **Configuration**: Set via `memory` field in agent configuration
- **Implementation**: Handled in `llm_quest_benchmark/llm/prompt.py`

### Tool System
- **Calculator**: Basic math operations via the calculator tool
- **Configuration**: Set via `tools` field in agent configuration
- **Implementation**: Tool handling in `llm_quest_benchmark/llm/prompt.py`

## Metrics Storage
- Primary storage in SQLite database: `metrics.db` (in project root)
  - Tables: `runs` (quest metadata) and `steps` (individual steps)
  - Analyze runs: `llm-quest analyze --last` or `llm-quest analyze --run-id <ID>`
  - Export: `llm-quest analyze --last --export report.json`
  - Format options: `--format summary|detail|compact`
- JSON backup exports at run completion:
  - Path format: `results/<agent_id>/<quest_name>/run_<ID>/`
  - Contains individual step files and `run_summary.json`
- Web interface uses separate SQLite database: `instance/llm_quest.sqlite`
- Benchmark results saved to `metrics/quests/benchmark_*.json`

## Working with Metrics
- Quick run inspection: `llm-quest analyze --last`
- View details: `llm-quest analyze --last --format detail`
- Export to JSON: `llm-quest analyze --last --export output.json`
- Analyze by quest: `llm-quest analyze --quest Boat.qm`
- Analyze benchmark: `llm-quest analyze --benchmark first`
- Raw SQL query: `sqlite3 metrics.db 'SELECT * FROM runs ORDER BY id DESC LIMIT 5'`

## Web Interface
- Start the server: `llm-quest server`
- Access the web UI at: http://localhost:8000
- The web interface provides:
  - Quest runner for interactive testing
  - Benchmark configuration and execution
  - Detailed analysis of quest runs and metrics
  - Visualization of agent performance
  - Export of run data for further analysis
- The server uses Flask and can be run in debug mode: `llm-quest server --debug`
- For production use: `llm-quest server --production --workers 4`

## Project Architecture Notes
- The `schemas` package contains all data models used throughout the system
- Avoid importing directly from the Python standard library `dataclasses` module to prevent circular imports
- Thread-safe database connections for metrics recording
- Schema migration support for database upgrades
- JSON export functionality for completed runs

## Current Development Tasks
- **Leaderboard Implementation (Phase 1 - Done)**:
  - ✅ Added database schema fields (response_time, token_usage, tool_usage_count, efficiency_score)
  - ✅ Created shared leaderboard service layer
  - ✅ Implemented CLI interface with new 'leaderboard' command
  - ✅ Added web interface with filtering and sorting
  - ✅ Added agent detail views for both CLI and web

## Shared Implementation Architecture
Implemented a shared service layer pattern using:

1. Core service: `LeaderboardService` class in `services/leaderboard.py`
   - Contains business logic for both CLI and web
   - Implemented interface-agnostic data processing and analysis

2. Database abstraction: `DBConnector` abstract class
   - `SQLiteConnector`: Used by CLI commands
   - `SQLAlchemyConnector`: Used by web interface
   - Allows sharing business logic while using the appropriate DB access

3. Interface implementations:
   - CLI: `executors/cli/leaderboard.py` with typer commands
   - Web: `web/views/leaderboard.py` with Flask routes

4. Visuals:
   - CLI: Rich tables for console display
   - Web: Bootstrap + Chart.js for browser display

### Key Files Added/Modified
- `/llm_quest_benchmark/services/leaderboard.py`: Core business logic
- `/llm_quest_benchmark/services/db_connectors.py`: Database abstraction
- `/llm_quest_benchmark/executors/cli/leaderboard.py`: CLI integration
- `/llm_quest_benchmark/web/views/leaderboard.py`: Web routes
- `/llm_quest_benchmark/web/templates/leaderboard/`: Web templates

### CLI Leaderboard Usage
```
# Show agent leaderboard with default sorting
llm-quest leaderboard show

# Filter by benchmark and sort by efficiency
llm-quest leaderboard show --benchmark first --sort efficiency_score

# Show details for a specific agent
llm-quest leaderboard agent my-agent-id
```

### Next Steps
- **Leaderboard Phase 2**:
  - Add more visualizations for comparative analysis
  - Implement A/B testing view
  - Add statistical significance indicators
  - Create automated leaderboard reports
