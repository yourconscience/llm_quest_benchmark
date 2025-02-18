"""Tests for quest runner"""
import logging
import pytest
from unittest.mock import MagicMock, patch

from llm_quest_benchmark.core.runner import QuestRunner
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.constants import DEFAULT_QUEST


@pytest.fixture
def mock_logger():
    """Mock logger for testing"""
    return MagicMock(spec=logging.Logger)


@pytest.fixture
def runner(mock_logger):
    """Create test runner instance"""
    return QuestRunner(logger=mock_logger)


def test_runner_initialization(runner):
    """Test runner initialization"""
    assert runner.env is None
    assert runner.agent is None
    assert runner.prompt_renderer is None
    assert runner.quest_logger is None
    assert runner.step_count == 0


def test_runner_error_handling(runner):
    """Test error handling in runner"""
    # Mock environment that raises an exception
    mock_env = MagicMock()
    mock_env.reset.side_effect = Exception("Test error")
    runner.env = mock_env

    outcome = runner.run()

    assert outcome == QuestOutcome.ERROR
    assert outcome.is_error
    assert outcome.exit_code == 2
    runner.logger.exception.assert_called_once()


def test_runner_successful_run(runner):
    """Test successful quest run"""
    # Mock successful environment and agent
    mock_env = MagicMock()
    mock_env.reset.return_value = True
    mock_env.step.return_value = (None, True, True, {})  # obs, done, success, info

    mock_agent = MagicMock()
    mock_agent.act.return_value = 0

    runner.env = mock_env
    runner.agent = mock_agent

    outcome = runner.run()

    assert outcome == QuestOutcome.SUCCESS
    assert not outcome.is_error
    assert outcome.exit_code == 0


def test_runner_failed_run(runner):
    """Test failed quest run"""
    # Mock environment that fails but doesn't error
    mock_env = MagicMock()
    mock_env.reset.return_value = True
    mock_env.step.return_value = (None, True, False, {})  # obs, done, success, info

    mock_agent = MagicMock()
    mock_agent.act.return_value = 0

    runner.env = mock_env
    runner.agent = mock_agent

    outcome = runner.run()

    assert outcome == QuestOutcome.FAILURE
    assert not outcome.is_error
    assert outcome.exit_code == 1


def test_runner_with_timeout(runner):
    """Test runner with timeout"""
    mock_env = MagicMock()
    mock_env.reset.return_value = True
    # Simulate environment that never finishes
    mock_env.step.return_value = (None, False, False, {})

    mock_agent = MagicMock()
    mock_agent.act.return_value = 0

    runner.env = mock_env
    runner.agent = mock_agent
    runner.timeout_seconds = 0.1  # Very short timeout

    outcome = runner.run()

    assert outcome == QuestOutcome.TIMEOUT
    assert outcome.is_error
    assert outcome.exit_code == 3