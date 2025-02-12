"""Tests for quest runner"""
import logging
import pytest
from unittest.mock import Mock, patch

from llm_quest_benchmark.core.runner import QuestRunner
from llm_quest_benchmark.constants import DEFAULT_QUEST


@pytest.fixture
def mock_logger():
    return Mock(spec=logging.Logger)


@pytest.fixture
def runner(mock_logger):
    return QuestRunner(logger=mock_logger)


def test_runner_initialization(runner, mock_logger):
    """Test that runner initializes correctly"""
    assert runner.logger == mock_logger
    assert runner.env is None
    assert runner.agent is None
    assert runner.renderer is None
    assert runner.metrics_logger is None


@patch('llm_quest_benchmark.environments.qm.QMPlayerEnv')
@patch('llm_quest_benchmark.agents.llm_agent.QuestAgent')
@patch('llm_quest_benchmark.renderers.quest_renderer.QuestRenderer')
def test_runner_setup(mock_renderer, mock_agent, mock_env, runner):
    """Test that runner sets up components correctly"""
    # Setup mocks
    mock_env_instance = Mock()
    mock_env.return_value = mock_env_instance
    mock_agent_instance = Mock()
    mock_agent.return_value = mock_agent_instance

    # Initialize
    runner.initialize(str(DEFAULT_QUEST))

    # Check that components were initialized
    mock_env.assert_called_once()
    mock_agent.assert_called_once()
    mock_renderer.assert_called_once()


@patch('llm_quest_benchmark.environments.qm.QMPlayerEnv')
@patch('llm_quest_benchmark.agents.llm_agent.QuestAgent')
def test_runner_execution(mock_agent, mock_env, runner):
    """Test quest execution flow"""
    # Setup mocks
    mock_env_instance = Mock()
    mock_env_instance.reset.return_value = {"observation": "test"}
    mock_env_instance.step.return_value = (
        {"observation": "next"},  # observations
        {0: 1.0},  # rewards
        True,  # done
        {}  # info
    )
    mock_env_instance.state.observations = [{"observation": "test"}]
    mock_env.return_value = mock_env_instance

    mock_agent_instance = Mock()
    mock_agent_instance.return_value = "1"
    mock_agent.return_value = mock_agent_instance

    # Initialize and run
    runner.initialize(str(DEFAULT_QUEST))
    exit_code = runner.run()

    # Verify execution flow
    mock_env_instance.reset.assert_called_once()
    mock_env_instance.step.assert_called_once_with("1")
    assert exit_code == 0  # Success due to positive reward


@patch('llm_quest_benchmark.environments.qm.QMPlayerEnv')
def test_runner_error_handling(mock_env, runner):
    """Test error handling during quest execution"""
    # Setup mock
    mock_env_instance = Mock()
    mock_env_instance.reset.side_effect = Exception("Test error")
    mock_env.return_value = mock_env_instance

    runner.initialize(str(DEFAULT_QUEST))
    exit_code = runner.run()

    assert exit_code == 1  # Failure due to error
    runner.logger.exception.assert_called_once()