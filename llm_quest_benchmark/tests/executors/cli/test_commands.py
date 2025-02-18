"""Tests for CLI commands"""
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from llm_quest_benchmark.executors.cli.commands import app
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.constants import DEFAULT_QUEST


@pytest.fixture
def cli_runner():
    """Create a CLI test runner"""
    return CliRunner()


def test_version_command(cli_runner):
    """Test version command"""
    result = cli_runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "llm-quest version" in result.stdout


def test_benchmark_command_errors(cli_runner, tmp_path):
    """Test benchmark command error handling"""
    # Test with non-existent config file
    result = cli_runner.invoke(app, [
        'benchmark',
        '--config', 'nonexistent.yaml'
    ])
    assert result.exit_code != 0
    assert "Config file does not exist" in result.stdout

    # Test with invalid config file
    config_path = tmp_path / "invalid_config.yaml"
    config_path.write_text("invalid: yaml: content")
    result = cli_runner.invoke(app, [
        'benchmark',
        '--config', str(config_path)
    ])
    assert result.exit_code != 0
    assert "Failed to load config" in result.stdout

    # Test with missing required argument
    result = cli_runner.invoke(app, ['benchmark'])
    assert result.exit_code != 0
    assert "Missing option '--config'" in result.stdout