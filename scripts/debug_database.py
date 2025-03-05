#!/usr/bin/env python
"""Check database tables and data from both CLI and web databases"""
import json
import logging
import sqlite3
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def check_database(db_path):
    """Check contents of a SQLite database"""
    logger.info(f"Checking database: {db_path}")

    if not Path(db_path).exists():
        logger.error(f"Database file does not exist: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get list of tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    logger.info(f"Tables: {[t[0] for t in tables]}")

    # Check runs schema
    try:
        cursor.execute("PRAGMA table_info(runs)")
        columns = cursor.fetchall()
        logger.info(f"Runs columns: {[c[1] for c in columns]}")

        # Check recent runs
        cursor.execute(
            "SELECT id, quest_name, agent_id, benchmark_id FROM runs ORDER BY id DESC LIMIT 5")
        runs = cursor.fetchall()
        logger.info(f"Recent runs: {runs}")

        # Check if any of these runs have steps
        for run in runs:
            run_id = run[0]
            cursor.execute(f"SELECT COUNT(*) FROM steps WHERE run_id = {run_id}")
            step_count = cursor.fetchone()[0]
            logger.info(f"Run {run_id} has {step_count} steps")
    except sqlite3.OperationalError as e:
        logger.error(f"Error checking runs: {e}")

    # Check benchmark_runs schema if it exists
    try:
        cursor.execute("PRAGMA table_info(benchmark_runs)")
        columns = cursor.fetchall()
        logger.info(f"Benchmark runs columns: {[c[1] for c in columns]}")

        # Check recent benchmarks
        cursor.execute(
            "SELECT id, benchmark_id, name, status FROM benchmark_runs ORDER BY id DESC LIMIT 5")
        benchmarks = cursor.fetchall()
        logger.info(f"Recent benchmarks: {benchmarks}")
    except sqlite3.OperationalError as e:
        logger.warning(f"No benchmark_runs table found: {e}")

    conn.close()


def main():
    # Check CLI database
    check_database(project_root / "metrics.db")

    # Check web database
    check_database(project_root / "instance/llm_quest.sqlite")

    # Add a test benchmark with benchmark_id explicitly set
    try:
        from llm_quest_benchmark.executors.benchmark import run_benchmark
        from llm_quest_benchmark.schemas.config import AgentConfig, BenchmarkConfig

        logger.info("Creating test benchmark with explicit benchmark_id")

        config = BenchmarkConfig(quests=["quests/kr1/Boat.qm"],
                                 agents=[AgentConfig(model="random_choice")],
                                 debug=True,
                                 max_workers=1,
                                 name="Test Benchmark",
                                 benchmark_id="test_benchmark_id_123")

        results = run_benchmark(config)
        logger.info(f"Benchmark complete with {len(results)} results")

        # Now check CLI database again to verify benchmark_id is set
        conn = sqlite3.connect(project_root / "metrics.db")
        cursor = conn.cursor()
        cursor.execute("SELECT agent_config FROM runs ORDER BY id DESC LIMIT 1")
        agent_config = cursor.fetchone()[0]
        if agent_config:
            config_dict = json.loads(agent_config)
            logger.info(f"Latest run agent_config: {config_dict}")
            logger.info(f"benchmark_id in config: {config_dict.get('benchmark_id')}")
        conn.close()

    except Exception as e:
        logger.error(f"Error running test benchmark: {e}")


if __name__ == "__main__":
    main()
