"""End-to-end tests for quest CLI"""
import logging
import pytest

from llm_quest_benchmark.constants import (
    DEFAULT_QUEST,
    DEFAULT_TEMPERATURE,
    DEFAULT_TEMPLATE,
)
from llm_quest_benchmark.core.runner import run_quest
from llm_quest_benchmark.executors.qm_player import play_quest
from llm_quest_benchmark.agents.random_agent import RandomAgent
from llm_quest_benchmark.environments.state import QuestOutcome


@pytest.mark.e2e
@pytest.mark.timeout(20)  # 20s should be enough
def test_quest_run_with_llm(caplog):
    """Test that quest runs with LLM agent and reaches a final state"""
    caplog.set_level(logging.DEBUG)  # Show all logs in test output

    # Run quest with real LLM agent
    outcome = run_quest(
        quest=str(DEFAULT_QUEST),
        debug=True,  # Enable debug logging
        headless=True,  # No UI needed for test
        temperature=DEFAULT_TEMPERATURE,
        model='gpt-4o-mini',  # Use faster model for tests
        template=DEFAULT_TEMPLATE,  # Use default template for faster execution
    )

    # Print logs for debugging
    print("\nDebug logs:")
    for record in caplog.records:
        print(f"{record.levelname}: {record.message}")

    # Check that we got a valid outcome
    assert not outcome.is_error, "Quest ended with an error"
    assert outcome in [QuestOutcome.SUCCESS, QuestOutcome.FAILURE], \
        "Quest did not reach a final state"
    assert outcome.exit_code == 0, "Normal quest outcomes should have exit code 0"


@pytest.mark.e2e
@pytest.mark.timeout(20)  # 20s should be enough
def test_quest_play_interactive(caplog):
    """Test interactive quest play reaches a final state using RandomAgent"""
    caplog.set_level("ERROR")  # Only show errors in test output

    # Use RandomAgent for automated testing
    player = RandomAgent(skip_single=True, debug=False)

    # Run quest with test player
    outcome = play_quest(
        quest=str(DEFAULT_QUEST),
        player=player,
        skip_single=True,
        debug=False
    )

    # Check that we got a valid outcome
    assert not outcome.is_error, "Quest ended with an error"
    assert outcome in [QuestOutcome.SUCCESS, QuestOutcome.FAILURE], \
        "Quest did not reach a final state"
    assert outcome.exit_code == 0, "Normal quest outcomes should have exit code 0"