"""End-to-end tests for benchmark functionality"""
import os
import json
from pathlib import Path

import pytest

from llm_quest_benchmark.executors.benchmark import run_benchmark
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.constants import DEFAULT_QUEST
from llm_quest_benchmark.executors.benchmark_config import BenchmarkConfig, AgentConfig


@pytest.mark.timeout(20)  # 20 seconds timeout for benchmark test
def test_benchmark_e2e():
    """Test end-to-end benchmark functionality."""
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
        max_workers=2
    )

    # Verify quest files exist
    for quest in config.quests:
        assert Path(quest).exists(), f"Quest file not found: {quest}"

    # Run benchmark
    results = run_benchmark(config)
    assert len(results) > 0, "No results returned"

    # Check metrics file was created
    metrics_dir = Path("metrics")
    assert metrics_dir.exists(), "Metrics directory not created"
    assert any(metrics_dir.glob("quest_run_*.jsonl")), "No metrics file created"