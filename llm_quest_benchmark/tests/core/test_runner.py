"""Tests for quest runner"""
import logging
import pytest
from unittest.mock import Mock, patch

from llm_quest_benchmark.core.runner import QuestRunner
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.constants import DEFAULT_QUEST, DEFAULT_TEMPERATURE, DEFAULT_TEMPLATE


@pytest.fixture
def mock_logger():
    return Mock(spec=logging.Logger)


@pytest.fixture
def runner(mock_logger):
    # Initialize with headless=True to match test expectations
    return QuestRunner(logger=mock_logger, headless=True)


def test_runner_initialization(runner, mock_logger):
    """Test that runner initializes correctly"""
    assert runner.logger == mock_logger
    assert runner.env is None
    assert runner.agent is None
    assert runner.terminal is None  # Now None because we set headless=True
    assert runner.prompt_renderer is None
    assert runner.quest_logger is None


@patch('llm_quest_benchmark.core.runner.QMPlayerEnv')
@patch('llm_quest_benchmark.core.runner.LLMAgent')
@patch('llm_quest_benchmark.core.runner.TerminalRenderer')
@patch('llm_quest_benchmark.core.runner.PromptRenderer')
def test_runner_setup(mock_prompt_renderer, mock_terminal, mock_agent, mock_env, runner):
    """Test that runner sets up components correctly"""
    # Setup mocks
    mock_env_instance = Mock()
    mock_env.return_value = mock_env_instance
    mock_agent_instance = Mock()
    mock_agent.return_value = mock_agent_instance
    mock_terminal_instance = Mock()
    mock_terminal.return_value = mock_terminal_instance
    mock_prompt_renderer_instance = Mock()
    mock_prompt_renderer.return_value = mock_prompt_renderer_instance

    # Initialize
    runner.initialize(str(DEFAULT_QUEST))

    # Check that components were initialized
    mock_env.assert_called_once()
    mock_agent.assert_called_once_with(
        debug=False,
        model_name='gpt-4o',
        template='default.jinja',
        skip_single=False,
        temperature=DEFAULT_TEMPERATURE
    )
    mock_prompt_renderer.assert_called_once()

    # Verify component instances were stored
    assert runner.env == mock_env_instance
    assert runner.agent == mock_agent_instance
    assert runner.prompt_renderer == mock_prompt_renderer_instance


@patch('llm_quest_benchmark.core.runner.QMPlayerEnv')
@patch('llm_quest_benchmark.core.runner.LLMAgent')
@patch('llm_quest_benchmark.core.runner.TerminalRenderer')
@patch('llm_quest_benchmark.core.runner.PromptRenderer')
def test_runner_execution(mock_prompt_renderer, mock_terminal, mock_agent, mock_env, runner):
    """Test quest execution flow - simplified to one step"""
    # Setup mocks
    mock_env_instance = Mock()
    mock_env_instance.reset.return_value = "Initial observation"
    mock_env_instance.step.return_value = (
        "Next observation",  # observations
        1.0,  # reward
        True,  # done - end after first step
        {}  # info
    )
    mock_env_instance.state = {'choices': [{'id': '1', 'text': 'Test choice'}]}
    mock_env.return_value = mock_env_instance

    mock_agent_instance = Mock()
    mock_agent_instance.get_action.return_value = "1"
    mock_agent_instance.history = []  # Add empty history
    mock_agent.return_value = mock_agent_instance

    mock_terminal_instance = Mock()
    mock_terminal.return_value = mock_terminal_instance

    mock_prompt_renderer_instance = Mock()
    mock_prompt_renderer_instance.render_action_prompt.return_value = "Test prompt"
    mock_prompt_renderer_instance.render_system_prompt.return_value = "Test system prompt"
    mock_prompt_renderer.return_value = mock_prompt_renderer_instance

    # Initialize and run
    runner.initialize(
        quest=str(DEFAULT_QUEST),
        model='gpt-4o-mini',  # Use faster model for tests
        template=DEFAULT_TEMPLATE,  # Use default template
        temperature=DEFAULT_TEMPERATURE
    )
    outcome = runner.run()

    # Verify execution flow
    mock_env_instance.reset.assert_called_once()
    mock_env_instance.step.assert_called_once_with("1")
    mock_agent_instance.get_action.assert_called_once_with(
        "Initial observation",
        mock_env_instance.state['choices']
    )
    mock_prompt_renderer_instance.render_action_prompt.assert_called_once_with(
        "Initial observation",
        mock_env_instance.state['choices']
    )
    assert outcome == QuestOutcome.SUCCESS  # Success due to positive reward


@patch('llm_quest_benchmark.core.runner.QMPlayerEnv')
def test_runner_error_handling(mock_env, runner):
    """Test error handling during quest execution"""
    # Setup mock
    mock_env_instance = Mock()
    mock_env_instance.reset.side_effect = Exception("Test error")
    mock_env.return_value = mock_env_instance

    runner.initialize(str(DEFAULT_QUEST))
    outcome = runner.run()

    assert outcome == QuestOutcome.ERROR  # Error due to exception
    runner.logger.exception.assert_called_once()