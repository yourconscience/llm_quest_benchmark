"""End-to-end tests for quest execution"""
import subprocess
import pytest

from llm_quest_benchmark.constants import DEFAULT_QUEST


@pytest.mark.integration
def test_quest_run_with_llm():
    """Test that quest runs with LLM agent"""
    result = subprocess.run([
        "llm-quest", "run",
        "-q", str(DEFAULT_QUEST),
        "--log-level", "debug",
        "--timeout", "5"  # Short timeout for testing
    ], capture_output=True, text=True)

    # Debug logs should show proper setup
    assert "Starting quest run with model" in result.stdout
    assert "Quest file:" in result.stdout


@pytest.mark.integration
def test_quest_play_interactive():
    """Test interactive quest play and verify debug logs show proper setup"""
    result = subprocess.run([
        "llm-quest", "play",
        "-q", str(DEFAULT_QUEST),
        "--log-level", "debug",
        "--skip"  # Auto-select single options
    ], capture_output=True, text=True)

    # Debug logs should show proper quest loading and interaction setup
    assert "Starting interactive quest play" in result.stdout
    assert "Quest file:" in result.stdout
    # Should show either interaction attempt or graceful exit
    assert any(x in result.stdout for x in [
        "Choices:",  # Shows interaction was ready
        "Quest ended",  # Or possible quick end
        "Error during interactive play"  # Or graceful error
    ])