"""End-to-end tests for quest CLI"""
import logging
import pytest

from llm_quest_benchmark.constants import (
    DEFAULT_QUEST,
    DEFAULT_TEMPERATURE,
    DEFAULT_TEMPLATE,
)
from llm_quest_benchmark.core.runner import run_quest_with_timeout
from llm_quest_benchmark.executors.qm_player import play_quest
from llm_quest_benchmark.agents.random_agent import RandomAgent
from llm_quest_benchmark.environments.state import QuestOutcome

TIMEOUT = 20


@pytest.mark.e2e
@pytest.mark.timeout(TIMEOUT)  # 20s should be enough
def test_quest_run_with_llm(caplog):
    """Test that quest runs with LLM agent and reaches a final state"""
    caplog.set_level(logging.DEBUG)  # Show all logs in test output

    # Run quest with real LLM agent
    result = run_quest_with_timeout(
        quest_path=str(DEFAULT_QUEST),
        model='gpt-4o-mini',  # Use faster model for tests
        template=DEFAULT_TEMPLATE,  # Use default template for faster execution
        temperature=DEFAULT_TEMPERATURE,
        timeout_seconds=TIMEOUT,  # Match the test timeout
        debug=True,  # Enable debug logging
        skip_single=True,  # Auto-select single choices
    )

    # Print logs for debugging
    print("\nDebug logs:")
    for record in caplog.records:
        print(f"{record.levelname}: {record.message}")

    # Convert string outcome back to enum
    outcome = QuestOutcome[result['outcome']]

    # Check that we got a valid outcome
    assert not outcome.is_error, f"Quest ended with an error: {result.get('error')}"
    assert outcome in [QuestOutcome.SUCCESS, QuestOutcome.FAILURE], \
        "Quest did not reach a final state"
    assert outcome.exit_code == 0, "Normal quest outcomes should have exit code 0"


@pytest.mark.e2e
@pytest.mark.timeout(TIMEOUT)h
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


@pytest.mark.e2e
@pytest.mark.timeout(TIMEOUT)
def test_random_agent_on_test_quest():
    """Test that random agent can complete a test quest"""
    # Run quest with random agent
    result = run_quest_with_timeout(
        quest_path=str(DEFAULT_QUEST),
        model="random_choice",
        debug=True,
        timeout_seconds=TIMEOUT,  # Match the test timeout
        skip_single=True,  # Auto-select single choices
    )

    # Convert string outcome back to enum
    outcome = QuestOutcome[result['outcome']]

    # Check that we got a valid outcome
    assert not outcome.is_error, f"Quest ended with an error: {result.get('error')}"
    assert outcome in [QuestOutcome.SUCCESS, QuestOutcome.FAILURE], \
        "Quest did not reach a final state"
    assert outcome.exit_code == 0, "Normal quest outcomes should have exit code 0"

    # Check steps were recorded
    assert len(result['steps']) > 0
    assert result['error'] is None