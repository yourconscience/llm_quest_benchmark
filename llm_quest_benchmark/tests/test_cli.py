"""Tests for CLI commands"""
import pytest
from typer.testing import CliRunner
from unittest.mock import patch

from llm_quest_benchmark.executors.cli.commands import app
from llm_quest_benchmark.constants import DEFAULT_QUEST


@pytest.fixture
def runner():
    return CliRunner(mix_stderr=False, echo_stdin=False)


def test_cli_help(runner):
    """Test that help command works"""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "llm-quest: Command-line tools" in result.stdout


@patch('llm_quest_benchmark.executors.qm_player.play_quest')
def test_play_command_starts(mock_play, runner):
    """Test that play command starts without error"""
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["play", "-q", str(DEFAULT_QUEST)], input="q\n")
        assert result.exit_code == 0
        mock_play.assert_called_once()


@patch('llm_quest_benchmark.core.runner.run_quest')
def test_run_command_starts(mock_run, runner):
    """Test that run command starts without error"""
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["run", "-q", str(DEFAULT_QUEST), "--timeout", "1"])
        assert result.exit_code == 0
        mock_run.assert_called_once()