"""End-to-end tests for quest CLI"""
import logging
import pytest
from typing import Any

from llm_quest_benchmark.constants import DEFAULT_QUEST, DEFAULT_TEMPLATE, SYSTEM_ROLE_TEMPLATE
from llm_quest_benchmark.core.runner import run_quest_with_timeout
from llm_quest_benchmark.agents.agent_factory import create_agent
from llm_quest_benchmark.environments.state import QuestOutcome

TIMEOUT = 20 # 20s should be enough for test quests to complete


@pytest.mark.e2e
@pytest.mark.timeout(TIMEOUT)
def test_quest_run_with_llm(caplog):
    """Test that quest runs with LLM agent and reaches a final state"""
    caplog.set_level(logging.DEBUG)  # Show all logs in test output

    # Create LLM agent
    agent = create_agent(
        model="random_choice",  # Use random for testing
        system_template=SYSTEM_ROLE_TEMPLATE,
        action_template=DEFAULT_TEMPLATE,
        temperature=0.0,
        skip_single=False,
        debug=True
    )
    assert agent is not None, "Failed to create agent"

    # Mock callback for testing
    def mock_callback(event: str, data: Any) -> None:
        if event == "progress":
            caplog.info(f"Progress update - Step {data['step']}: {data['message']}")
        elif event == "game_state":
            caplog.info(f"Game state update - Step {data.step}")
        elif event == "error":
            caplog.error(f"Error: {data}")

    # Run quest with real LLM agent
    try:
        outcome = run_quest_with_timeout(
            quest_path=str(DEFAULT_QUEST),
            agent=agent,
            timeout=TIMEOUT,  # Match the test timeout
            debug=True,  # Enable debug logging
            callbacks=[mock_callback]
        )

        # Check that we got a valid outcome
        assert outcome is not None, "Quest returned no outcome"
        assert not outcome.is_error, f"Quest ended with an error: {caplog.text}"
        assert outcome in [QuestOutcome.SUCCESS, QuestOutcome.FAILURE], \
            f"Quest did not reach a final state. State: {outcome}"
        assert outcome.exit_code == 0, f"Quest should have a successful exit code, got {outcome.exit_code}"

    except Exception as e:
        pytest.fail(f"Quest run failed with error: {e}\nLogs:\n{caplog.text}")


@pytest.mark.e2e
@pytest.mark.timeout(TIMEOUT)
def test_random_agent_on_test_quest(caplog):
    """Test that random agent can complete a test quest"""
    caplog.set_level(logging.DEBUG)  # Show all logs in test output

    # Create random agent
    agent = create_agent("random_choice", skip_single=True, debug=True)
    assert agent is not None, "Failed to create random agent"

    # Mock callback for testing
    def mock_callback(event: str, data: Any) -> None:
        if event == "progress":
            caplog.info(f"Progress update - Step {data['step']}: {data['message']}")
        elif event == "game_state":
            caplog.info(f"Game state update - Step {data.step}")
        elif event == "error":
            caplog.error(f"Error: {data}")

    # Run quest with random agent
    try:
        outcome = run_quest_with_timeout(
            quest_path=str(DEFAULT_QUEST),
            agent=agent,
            debug=True,  # Enable debug logging
            timeout=TIMEOUT,  # Match the test timeout
            callbacks=[mock_callback]
        )

        # Check that we got a valid outcome
        assert outcome is not None, "Quest returned no outcome"
        assert not outcome.is_error, f"Quest ended with an error: {caplog.text}"
        assert outcome in [QuestOutcome.SUCCESS, QuestOutcome.FAILURE], \
            f"Quest did not reach a final state. State: {outcome}"
        assert outcome.exit_code == 0, f"Quest should have a successful exit code, got {outcome.exit_code}"

    except Exception as e:
        pytest.fail(f"Quest run failed with error: {e}\nLogs:\n{caplog.text}")