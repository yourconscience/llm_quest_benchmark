"""End-to-end tests for benchmark functionality"""

import logging
from pathlib import Path

import pytest

from llm_quest_benchmark.executors.benchmark import run_benchmark
from llm_quest_benchmark.executors.benchmark_config import BenchmarkConfig, AgentConfig


@pytest.mark.timeout(20)  # 20 seconds timeout for benchmark test
def test_benchmark_e2e(caplog):
    """Test end-to-end benchmark functionality."""
    caplog.set_level(logging.DEBUG)  # Show all logs in test output

    config = BenchmarkConfig(
        quests=["quests/boat.qm"],
        agents=[
            AgentConfig(
                model="gpt-4o-mini",
                template="default.jinja",
                temperature=0.3,
                skip_single=True
            ),
            AgentConfig(
                model="random_choice",
                template="default.jinja",
                temperature=0.0,
                skip_single=True
            )
        ],
        timeout_seconds=20,
        max_workers=2,
        debug=True  # Enable debug mode
    )

    # Verify quest files exist
    for quest in config.quests:
        quest_path = Path(quest)
        assert quest_path.exists(), f"Quest file not found: {quest}"
        print(f"\nFound quest file: {quest_path.absolute()}")

    try:
        # Run benchmark
        results = run_benchmark(config)
        assert len(results) > 0, "No results returned"
    except Exception as e:
        print(f"\nBenchmark failed with error: {str(e)}")
        raise e

    # Check metrics file was created
    metrics_dir = Path("metrics")
    assert metrics_dir.exists(), "Metrics directory not created"
    assert any(metrics_dir.glob("quest_run_*.jsonl")), "No metrics file created"