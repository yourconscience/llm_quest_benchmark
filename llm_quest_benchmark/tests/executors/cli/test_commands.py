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
    assert result.exit_code in [0, 1]  # Success or failure is fine, just not error
    assert "Running quest:" in result.stdout

def test_run_quest_invalid_args():
    """Test run command with invalid arguments"""
    # Test invalid model
    result = runner.invoke(app, [
        "run",
        "--quest", str(DEFAULT_QUEST),
        "--model", "invalid-model"
    ])
    assert result.exit_code == 2
    assert "Error during quest run" in result.stdout

    # Test missing quest file
    result = runner.invoke(app, [
        "run",
        "--quest", "nonexistent.qm",
        "--model", "random_choice"
    ])
    assert result.exit_code == 2
    assert "Error during quest run" in result.stdout

def test_analyze_invalid_input():
    """Test analyze command with invalid input"""
    result = runner.invoke(app, ["analyze"])
    assert result.exit_code == 1
    assert "Must specify either --quest or --benchmark" in result.stdout

def test_benchmark_missing_config():
    """Test benchmark command with missing config"""
    result = runner.invoke(app, ["benchmark", "--config", "nonexistent.yaml"])
    assert result.exit_code == 1
    assert "Config file does not exist" in result.stdout

def test_server_command():
    """Test server command options"""
    # Test help output
    result = runner.invoke(app, ["server", "--help"])
    assert result.exit_code == 0
    assert "Start the web interface server" in result.stdout

    # Test invalid host
    result = runner.invoke(app, ["server", "--host", "invalid"])
    assert result.exit_code == 1
    assert "nodename nor servname provided" in result.stdout