"""End-to-end tests for benchmark functionality"""
import os
import json
from pathlib import Path

import pytest

from llm_quest_benchmark.executors.benchmark import run_benchmark
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.constants import DEFAULT_QUEST
from llm_quest_benchmark.executors.benchmark_config import BenchmarkConfig, AgentConfig


@pytest.mark.timeout(30)  # 30 seconds timeout for benchmark test
def test_benchmark_e2e(tmp_path):
    """Test benchmark functionality with real agents on two short quests"""
    # Use Boat.qm and Gladiator.qm from kr1 as test quests
    quest_files = [
        DEFAULT_QUEST,
        "quests/kr1/Gladiator.qm"
    ]
    for quest in quest_files:
        assert Path(quest).exists(), f"Quest file not found: {quest}"

    # Create benchmark config
    config = BenchmarkConfig(
        quests=quest_files,
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
        debug=False,
        timeout_seconds=10,  # 10 seconds per quest should be enough
        max_workers=2,
        output_dir=str(tmp_path / "metrics")
    )

    # Run benchmark
    results = run_benchmark(config)

    # Verify results
    assert len(results) == 4, "Expected results for 2 models × 2 quests"
    assert all(r['quest'] in ["Boat.qm", "Gladiator.qm"] for r in results), "Quest name mismatch"
    assert all(r['model'] in ["gpt-4o-mini", "random_choice"] for r in results), "Model name mismatch"
    assert all(r['template'] == "default.jinja" for r in results), "Template mismatch"
    assert all(r['temperature'] in [0.3, 0.0] for r in results), "Temperature mismatch"
    assert all(r['outcome'] in [o.name for o in QuestOutcome] for r in results), "Invalid outcome"

    # Verify output files
    output_dir = tmp_path / "metrics"
    assert output_dir.exists(), "Output directory not created"
    output_files = list(output_dir.glob("benchmark_*.jsonl"))
    assert len(output_files) == 1, "Expected one output file"

    # Verify file contents
    with open(output_files[0], 'r', encoding='utf-8') as f:
        lines = f.readlines()
        assert len(lines) == 4, "Expected 4 result entries"
        for line in lines:
            result = json.loads(line)
            assert result['quest'] in ["Boat.qm", "Gladiator.qm"], "Quest name mismatch in output file"
            assert result['model'] in ["gpt-4o-mini", "random_choice"], "Model name mismatch in output file"
            assert result['template'] == "default.jinja", "Template mismatch in output file"
            assert result['temperature'] in [0.3, 0.0], "Temperature mismatch in output file"
            assert result['outcome'] in [o.name for o in QuestOutcome], "Invalid outcome in output file"