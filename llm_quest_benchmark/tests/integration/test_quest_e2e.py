"""End-to-end tests for quest CLI"""
import subprocess
import pytest
from unittest.mock import patch

from llm_quest_benchmark.constants import DEFAULT_QUEST
from llm_quest_benchmark.executors.qm_player import play_quest
from llm_quest_benchmark.tests.agents.test_players import FirstChoicePlayer


@pytest.mark.e2e
@pytest.mark.timeout(20)  # 20s should be enough
def test_quest_run_with_llm(caplog):
    """Test that quest runs with LLM agent and reaches a final state"""
    caplog.set_level("ERROR")  # Only show errors in test output

    result = subprocess.run([
        "llm-quest", "run",
        "-q", str(DEFAULT_QUEST),
        "--log-level", "error",  # Reduce CLI output
    ], capture_output=True, text=True)

    # Check that we reached a final state (success or failure)
    final_state_reached = False
    for line in result.stdout.splitlines():
        if "Quest completed" in line or "Quest failed" in line:
            final_state_reached = True
            break

    assert final_state_reached, \
        f"Quest did not reach final state. Output:\n{result.stdout}\nErrors:\n{result.stderr}"


@pytest.mark.e2e
@pytest.mark.timeout(20)  # 20s should be enough
def test_quest_play_interactive(caplog):
    """Test interactive quest play reaches a final state using FirstChoicePlayer"""
    caplog.set_level("ERROR")  # Only show errors in test output

    # Use FirstChoicePlayer for automated testing
    player = FirstChoicePlayer(skip_single=True, debug=False)

    # Run quest with test player
    outcome = play_quest(
        quest_path=str(DEFAULT_QUEST),
        language="eng",  # Use English for testing
        player=player,
        metrics=False,
        debug=False
    )

    # Check that we got a valid outcome
    assert outcome is not None, "Quest did not return an outcome"