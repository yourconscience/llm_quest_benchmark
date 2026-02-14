"""Tests for CLI commands"""
import pytest
from typer.testing import CliRunner
from pathlib import Path
from llm_quest_benchmark.executors.cli.commands import app
from llm_quest_benchmark.constants import DEFAULT_QUEST

runner = CliRunner(mix_stderr=False)

def test_version():
    """Test version command"""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "llm-quest version" in result.stdout

def test_run_quest():
    """Test running a quest with random agent"""
    result = runner.invoke(app, [
        "run",
        "--quest", str(DEFAULT_QUEST),
        "--model", "random_choice",
        "--debug"
    ])
    assert result.exit_code in [0, 1, 2]

def test_run_quest_invalid_args():
    """Test run command with invalid arguments"""
    # Test invalid model
    result = runner.invoke(app, [
        "run",
        "--quest", str(DEFAULT_QUEST),
        "--model", "invalid-model"
    ])
    assert result.exit_code == 2

    # Test missing quest file
    result = runner.invoke(app, [
        "run",
        "--quest", "nonexistent.qm",
        "--model", "random_choice"
    ])
    assert result.exit_code == 2

def test_analyze_invalid_input():
    """Test analyze command with invalid input"""
    result = runner.invoke(app, ["analyze"])
    assert result.exit_code == 1
    assert "Must specify one of: --quest, --benchmark, --run-id, or --last" in result.stderr

def test_benchmark_missing_config():
    """Test benchmark command with missing config"""
    result = runner.invoke(app, ["benchmark", "--config", "nonexistent.yaml"])
    assert result.exit_code == 1
    assert "Config file does not exist" in result.stdout or "Config file does not exist" in result.stderr

def test_server_command():
    """Test server command options"""
    # Test help output
    result = runner.invoke(app, ["server", "--help"])
    assert result.exit_code == 0
    assert "Start the Flask web interface server" in result.stdout

    # Test invalid host
    result = runner.invoke(app, ["server", "--host", "invalid"])
    assert result.exit_code == 1
    assert "Starting server on http://invalid:8000" in result.stdout


def test_analyze_run_with_run_summary_path(tmp_path):
    """Test analyze-run against explicit run_summary path."""
    summary_path = tmp_path / "run_summary.json"
    summary_path.write_text(
        """
{
  "quest_name": "TestQuest",
  "agent_id": "llm_test",
  "outcome": "FAILURE",
  "steps": [
    {
      "step": 1,
      "observation": "State one",
      "choices": {"1": "Go left", "2": "Go right"},
      "llm_decision": {
        "analysis": "Need progress",
        "reasoning": "Right seems safer",
        "is_default": false,
        "choice": {"2": "Go right"}
      }
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["analyze-run", "--run-summary", str(summary_path)])
    assert result.exit_code == 0
    assert "Decision Steps: 1" in result.stdout
    assert "selected [2:Go right]" in result.stdout


def test_analyze_run_autolocates_latest_run(monkeypatch, tmp_path):
    """Test analyze-run latest-run discovery with --agent and --quest."""
    monkeypatch.chdir(tmp_path)
    run_dir = tmp_path / "results" / "llm_test" / "QuestA" / "run_42"
    run_dir.mkdir(parents=True)
    summary_path = run_dir / "run_summary.json"
    summary_path.write_text(
        """
{
  "quest_name": "QuestA",
  "agent_id": "llm_test",
  "outcome": "SUCCESS",
  "steps": []
}
""".strip(),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["analyze-run", "--agent", "llm_test", "--quest", "QuestA"])
    assert result.exit_code == 0
    assert "Outcome: SUCCESS" in result.stdout
