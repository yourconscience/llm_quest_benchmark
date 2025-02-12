"""Smoke tests for CLI commands"""
import pytest
from typer.testing import CliRunner

from llm_quest_benchmark.executors.cli.commands import app
from llm_quest_benchmark.constants import DEFAULT_QUEST

runner = CliRunner()

def test_cli_help():
    """Test that CLI help works"""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "llm-quest: Command-line tools" in result.stdout

def test_play_command_starts():
    """Test that play command starts without error"""
    result = runner.invoke(app, ["play", "-q", str(DEFAULT_QUEST)], input="q\n")
    assert "Starting interactive quest play" in result.stdout

def test_run_command_starts():
    """Test that run command starts without error"""
    result = runner.invoke(app, ["run", "-q", str(DEFAULT_QUEST), "--timeout", "1"])
    assert "Starting quest run with model" in result.stdout