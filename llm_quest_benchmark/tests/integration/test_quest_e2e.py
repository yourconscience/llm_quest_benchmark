"""End-to-end tests for quest CLI"""
import logging
import pytest

from llm_quest_benchmark.constants import DEFAULT_QUEST, DEFAULT_QUEST_TIMEOUT
from llm_quest_benchmark.core.runner import run_quest_with_timeout
from llm_quest_benchmark.agents.agent_factory import create_agent
from llm_quest_benchmark.environments.state import QuestOutcome

TIMEOUT = 15 # 15s should be enough for test quests to complete


@pytest.mark.e2e
@pytest.mark.timeout(TIMEOUT)
def test_quest_run_with_llm(caplog):
    """Test that quest runs with LLM agent and reaches a final state"""
    caplog.set_level(logging.DEBUG)  # Show all logs in test output

    # Create LLM agent
    agent = create_agent("gpt-4o-mini", skip_single=True, debug=True)  # Use faster model for tests
    assert agent is not None, "Failed to create agent"

    # Run quest with real LLM agent
    result = run_quest_with_timeout(
        quest_path=str(DEFAULT_QUEST),
        agent=agent,
        timeout=TIMEOUT,  # Match the test timeout
        debug=True,  # Enable debug logging
    )

    # Convert string outcome back to enum
    outcome = QuestOutcome[result['outcome']]

    # Check that we got a valid outcome
    assert not outcome.is_error, f"Quest ended with an error: {result.get('error')}"
    assert outcome in [QuestOutcome.SUCCESS, QuestOutcome.FAILURE], \
        "Quest did not reach a final state"
    assert outcome.exit_code == 0, "Normal quest outcomes should have exit code 0"


@pytest.mark.e2e
@pytest.mark.timeout(TIMEOUT)
def test_random_agent_on_test_quest(caplog):
    """Test that random agent can complete a test quest"""
    caplog.set_level(logging.DEBUG)  # Show all logs in test output

    # Create random agent
    agent = create_agent("random_choice", skip_single=True, debug=True)
    assert agent is not None, "Failed to create random agent"

    # Run quest with random agent
    result = run_quest_with_timeout(
        quest_path=str(DEFAULT_QUEST),
        agent=agent,
        debug=True,  # Enable debug logging
        timeout=TIMEOUT,  # Match the test timeout
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