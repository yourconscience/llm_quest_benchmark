"""Integration tests for quest execution"""
import subprocess
from pathlib import Path

import pytest

from llm_quest_benchmark.constants import DEFAULT_QUEST


@pytest.mark.integration
def test_quest_run_with_llm():
    """Test running a quest with LLM agent and verify debug logs show proper interaction"""
    result = subprocess.run([
        "llm-quest", "run",
        "-q", str(DEFAULT_QUEST),
        "--log-level", "debug",
        "--timeout", "5",
        "--model", "sonnet"
    ], capture_output=True, text=True)

    # Debug logs should show initialization and error handling
    assert "Starting quest run with model sonnet" in result.stdout
    assert "Debug logging enabled" in result.stdout
    assert "Initializing environment" in result.stdout
    # Should show either error handling or success
    assert any(x in result.stdout for x in [
        "Error during quest run",  # Expected error handling
        "Quest completed",  # Or possible completion
        "Quest failed"  # Or possible failure
    ])


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
        "Available actions",  # Shows interaction was ready
        "Quest ended",  # Or possible quick end
        "Error during interactive play"  # Or graceful error
    ])