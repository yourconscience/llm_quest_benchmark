"""End-to-end tests for quest CLI"""
import logging
import pytest
from unittest.mock import patch, Mock

from llm_quest_benchmark.constants import DEFAULT_QUEST
from llm_quest_benchmark.core.runner import run_quest
from llm_quest_benchmark.executors.qm_player import play_quest
from llm_quest_benchmark.tests.agents.test_players import FirstChoicePlayer
from llm_quest_benchmark.environments.state import QuestOutcome


@pytest.mark.e2e
@pytest.mark.timeout(20)  # 20s should be enough
@patch('llm_quest_benchmark.core.runner.LLMAgent')
def test_quest_run_with_llm(mock_agent_class, caplog):
    """Test that quest runs with LLM agent and reaches a final state"""
    caplog.set_level("ERROR")  # Only show errors in test output

    # Set up mock agent
    mock_agent = Mock()
    mock_agent.get_action.return_value = "1"  # Always choose first option
    mock_agent_class.return_value = mock_agent

    # Run quest directly
    outcome = run_quest(
        quest=str(DEFAULT_QUEST),
        debug=False,  # Reduce output
        headless=True,  # No UI needed for test
    )

    # Check that we got a valid outcome
    assert outcome in [QuestOutcome.SUCCESS, QuestOutcome.FAILURE], \
        "Quest did not reach a final state"

    # Verify agent was used
    assert mock_agent.get_action.called, "Agent's get_action was not called"


@pytest.mark.e2e
@pytest.mark.timeout(20)  # 20s should be enough
def test_quest_play_interactive(caplog):
    """Test interactive quest play reaches a final state using FirstChoicePlayer"""
    caplog.set_level("ERROR")  # Only show errors in test output

    # Use FirstChoicePlayer for automated testing
    player = FirstChoicePlayer(skip_single=True, debug=False)

    # Run quest with test player
    outcome = play_quest(
        quest=str(DEFAULT_QUEST),
        player=player,
        skip_single=True,
        debug=False
    )

    # Check that we got a valid outcome
    assert outcome in [QuestOutcome.SUCCESS, QuestOutcome.FAILURE], \
        "Quest did not reach a final state"