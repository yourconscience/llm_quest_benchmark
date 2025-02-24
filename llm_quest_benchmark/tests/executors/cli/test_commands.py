"""Tests for CLI commands"""
import pytest
from typer.testing import CliRunner
from pathlib import Path
from llm_quest_benchmark.executors.cli.commands import app
from llm_quest_benchmark.constants import DEFAULT_QUEST

runner = CliRunner()

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
    assert "Starting quest run with agent" in result.stdout

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

def test_server_help():
    """Test server command help"""
    result = runner.invoke(app, ["server", "--help"])
    assert result.exit_code == 0
    assert "Start the web interface server" in result.stdout