"""Tests for quest run analyzer"""
import json
from pathlib import Path
from typer.testing import CliRunner

from llm_quest_benchmark.executors.cli.commands import app
from llm_quest_benchmark.core.analyzer import analyze_quest_run


def test_analyze_metrics(tmp_path):
    """Test analyze command with a valid metrics file"""
    # Create test metrics file
    metrics_dir = tmp_path / "metrics"
    metrics_dir.mkdir()
    metrics_file = metrics_dir / "quest_run_20250217_144717.jsonl"

    # Create example metrics data
    steps = [
        {
            "step": 1,
            "timestamp": "2025-02-17T14:47:17.123456",
            "state": "You are at a trading station.",
            "choices": [{"id": "1", "text": "Talk to merchant"}, {"id": "2", "text": "Leave station"}],
            "prompt": "Test prompt",
            "response": "1",
            "reward": 0.5,
            "metrics": {"time_taken": 1.2},
            "is_llm": True,
            "quest_file": "test_quest.qm",
            "model": "test-model",
            "template": "test-template"
        },
        {
            "step": 2,
            "timestamp": "2025-02-17T14:47:18.123456",
            "state": "The merchant greets you.",
            "choices": [{"id": "1", "text": "Buy"}, {"id": "2", "text": "Sell"}],
            "prompt": "Test prompt 2",
            "response": "2",
            "reward": 1.0,
            "metrics": {"time_taken": 0.8},
            "is_llm": True
        }
    ]

    # Write JSONL file
    with open(metrics_file, "w") as f:
        for step in steps:
            f.write(json.dumps(step, ensure_ascii=False) + "\n")

    # Test analyze_quest_run function
    results = analyze_quest_run(metrics_file)
    assert results["summary"]["quest_file"] == "test_quest.qm"
    assert results["summary"]["player_type"] == "LLM Agent"
    assert results["summary"]["model"] == "test-model"
    assert results["summary"]["template"] == "test-template"
    assert results["summary"]["total_steps"] == 2
    assert results["summary"]["outcome"] == "SUCCESS"
    assert len(results["steps"]) == 2

    # Test CLI command
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["analyze", "--quest", str(metrics_file)])
        assert result.exit_code == 0

        # Check that summary info is present
        assert "Quest Run Summary" in result.stdout
        assert "Total Steps: 2" in result.stdout
        assert "Model: test-model" in result.stdout
        assert "Template: test-template" in result.stdout
        assert "Outcome: SUCCESS" in result.stdout

        # Check that step info is present
        assert "Step 1:" in result.stdout
        assert "Action: 1" in result.stdout
        assert "Step 2:" in result.stdout
        assert "Action: 2" in result.stdout


def test_analyze_no_metrics_dir(tmp_path):
    """Test analyze command with no metrics directory"""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["analyze"])
        assert result.exit_code == 1
        assert "No benchmark files found" in result.stdout


def test_analyze_empty_metrics_dir(tmp_path):
    """Test analyze command with empty metrics directory"""
    metrics_dir = tmp_path / "metrics"
    metrics_dir.mkdir()

    runner = CliRunner()
    with runner.isolated_filesystem():
        metrics_dir = Path("metrics")
        metrics_dir.mkdir()
        result = runner.invoke(app, ["analyze"])
        assert result.exit_code == 1
        assert "No benchmark files found" in result.stdout


def test_analyze_invalid_file(tmp_path):
    """Test analyze command with invalid metrics file"""
    metrics_file = tmp_path / "invalid.jsonl"
    metrics_file.write_text("invalid json")

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["analyze", "--quest", str(metrics_file)])
        assert result.exit_code == 1
        assert "Error analyzing metrics" in result.stdout


def test_analyze_both_params(tmp_path):
    """Test analyze command with both quest and benchmark parameters"""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["analyze", "--quest", "test.jsonl", "--benchmark", "test.json"])
        assert result.exit_code == 1
        assert "Cannot specify both --quest and --benchmark" in result.stdout


def test_analyze_invalid_benchmark_file(tmp_path):
    """Test analyze command with invalid benchmark file type"""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["analyze", "--benchmark", "test.txt"])
        assert result.exit_code == 1
        assert "Benchmark file must be a .json file" in result.stdout


def test_analyze_benchmark_directory(tmp_path):
    """Test analyze command with benchmark directory"""
    # Create benchmark directory with a test file
    benchmark_dir = tmp_path / "metrics" / "benchmarks"
    benchmark_dir.mkdir(parents=True)
    benchmark_file = benchmark_dir / "benchmark_20250217_144717.json"
    benchmark_file.write_text("{}")  # Empty but valid JSON

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["analyze", "--benchmark", str(benchmark_dir)])
        assert result.exit_code == 0