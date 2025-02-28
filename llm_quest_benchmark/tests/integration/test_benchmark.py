"""End-to-end tests for benchmark functionality"""

import logging
from pathlib import Path

import pytest

from llm_quest_benchmark.executors.benchmark import run_benchmark
from llm_quest_benchmark.schemas.config import BenchmarkConfig, AgentConfig
from llm_quest_benchmark.constants import (
    SYSTEM_ROLE_TEMPLATE,
    DEFAULT_TEMPLATE
)


@pytest.mark.timeout(20)  # 20 seconds timeout for benchmark test
def test_benchmark_e2e(caplog, tmp_path):
    """Test end-to-end benchmark functionality."""
    caplog.set_level(logging.DEBUG)  # Show all logs in test output

    # Create a test quest file
    quest_path = tmp_path / "test_quest.qm"
    quest_path.write_text("""
    [start]
    text: You are in a room.
    choices:
        - Go north: room1
        - Go south: room2

    [room1]
    text: You found the treasure!
    success: true

    [room2]
    text: Dead end.
    failure: true
    """)

    config = BenchmarkConfig(
        quests=[str(quest_path)],
        agents=[
            AgentConfig(
                model="random_choice",  # Use random_choice for testing
                system_template=SYSTEM_ROLE_TEMPLATE,
                action_template=DEFAULT_TEMPLATE,
                temperature=0.0,
                skip_single=True
            )
        ],
        quest_timeout=5,
        max_workers=1,
        debug=True,
        output_dir=str(tmp_path)
    )

    try:
        # Run benchmark
        results = run_benchmark(config)

        # Verify results
        assert len(results) > 0, "No results returned"
        assert len(results) == len(config.agents), f"Expected {len(config.agents)} results, got {len(results)}"

        # Check first result
        result = results[0]
        assert result['quest'] == str(quest_path)
        assert result['model'] == "random_choice"
        assert result['temperature'] == 0.0
        assert result['template'] == SYSTEM_ROLE_TEMPLATE
        assert 'agent_id' in result
        assert 'outcome' in result

        # Check metrics file was created
        assert any(tmp_path.glob("benchmark_*.json")), "No metrics file created"

    except Exception as e:
        print(f"\nBenchmark failed with error: {str(e)}")
        raise e