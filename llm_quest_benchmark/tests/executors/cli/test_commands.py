"""Tests for CLI commands"""
import os
import json
from pathlib import Path
from typing import List
from unittest.mock import patch, Mock

import pytest
from typer.testing import CliRunner

from llm_quest_benchmark.executors.cli.commands import app
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.constants import DEFAULT_QUEST


@pytest.fixture
def cli_runner():
    """Create a CLI test runner"""
    return CliRunner()


@pytest.fixture
def mock_benchmark_results() -> List[dict]:
    """Mock benchmark results"""
    return [
        {
            'quest': 'Boat.qm',
            'model': 'gpt-4o-mini',
            'template': 'default.jinja',
            'temperature': 0.3,
            'outcome': QuestOutcome.SUCCESS.name,
            'error': None,
            'timestamp': '2024-02-17T20:02:15.123456'
        },
        {
            'quest': 'Boat.qm',
            'model': 'random_choice',
            'template': 'default.jinja',
            'temperature': 0.0,
            'outcome': QuestOutcome.FAILURE.name,
            'error': None,
            'timestamp': '2024-02-17T20:02:16.123456'
        }
    ]


def test_benchmark_command(cli_runner, tmp_path, mock_benchmark_results):
    """Test benchmark command with config file"""
    # Create a test config file
    config_path = tmp_path / "test_config.yaml"
    config_content = """
    quests:
      - quests/kr1/Boat.qm
      - quests/kr1/Gladiator.qm
    agents:
      - model: gpt-4o-mini
        template: default.jinja
        temperature: 0.3
        skip_single: true
      - model: random_choice
        template: default.jinja
        temperature: 0.0
        skip_single: true
    debug: false
    timeout_seconds: 10
    max_workers: 2
    output_dir: metrics
    """
    config_path.write_text(config_content)

    # Mock benchmark function
    with patch('llm_quest_benchmark.executors.cli.commands.run_benchmark') as mock_run:
        mock_run.return_value = mock_benchmark_results

        # Run command
        result = cli_runner.invoke(app, [
            'benchmark',
            '--config', str(config_path)
        ])

        # Check command succeeded
        assert result.exit_code == 0, f"Command failed with: {result.stdout}"

        # Verify benchmark was called with correct config
        mock_run.assert_called_once()
        config = mock_run.call_args[0][0]
        assert len(config.quests) == 2
        assert config.quests[0] == "quests/kr1/Boat.qm"
        assert config.quests[1] == "quests/kr1/Gladiator.qm"
        assert len(config.agents) == 2
        assert config.agents[0].model == "gpt-4o-mini"
        assert config.agents[1].model == "random_choice"
        assert config.timeout_seconds == 10
        assert config.max_workers == 2


def test_benchmark_command_with_debug_override(cli_runner, tmp_path, mock_benchmark_results):
    """Test benchmark command with debug flag override"""
    # Create a test config file with debug: false
    config_path = tmp_path / "test_config.yaml"
    config_content = """
    quests:
      - quests/kr1/Boat.qm
    agents:
      - model: gpt-4o-mini
        template: default.jinja
        temperature: 0.3
    debug: false
    timeout_seconds: 10
    max_workers: 2
    output_dir: metrics
    """
    config_path.write_text(config_content)

    # Mock benchmark function
    with patch('llm_quest_benchmark.executors.cli.commands.run_benchmark') as mock_run:
        mock_run.return_value = mock_benchmark_results

        # Run command with debug flag
        result = cli_runner.invoke(app, [
            'benchmark',
            '--config', str(config_path),
            '--debug'
        ])

        # Check command succeeded
        assert result.exit_code == 0, f"Command failed with: {result.stdout}"

        # Verify debug was overridden
        mock_run.assert_called_once()
        config = mock_run.call_args[0][0]
        assert config.debug is True


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