"""Tests for quest runner"""
import logging
import pytest
from unittest.mock import Mock, patch

from llm_quest_benchmark.core.runner import QuestRunner
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.constants import DEFAULT_QUEST


@pytest.fixture
def mock_logger():
    return Mock(spec=logging.Logger)


@pytest.fixture
def runner(mock_logger):
    return QuestRunner(logger=mock_logger, headless=True)


def test_runner_initialization(runner, mock_logger):
    """Test that runner initializes correctly"""
    assert runner.logger == mock_logger
    assert runner.env is None
    assert runner.agent is None
    assert runner.terminal is None
    assert runner.prompt_renderer is None
    assert runner.quest_logger is None


@patch('llm_quest_benchmark.core.runner.QMPlayerEnv')
def test_runner_error_handling(mock_env, runner):
    """Test error handling during quest execution"""
    mock_env_instance = Mock()
    mock_env_instance.reset.side_effect = Exception("Test error")
    mock_env.return_value = mock_env_instance

    runner.initialize(str(DEFAULT_QUEST))
    outcome = runner.run()

    assert outcome == QuestOutcome.ERROR
    assert outcome.is_error
    assert outcome.exit_code == 2
    runner.logger.exception.assert_called_once()