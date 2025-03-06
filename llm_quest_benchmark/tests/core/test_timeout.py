"""Tests for time module"""
import pytest
import time

from llm_quest_benchmark.core.time import timeout, CommandTimeout


def test_timeout_context_manager():
    """Test that timeout context manager works"""
    # Test successful completion within timeout
    with timeout(1):
        time.sleep(0.1)  # Should complete successfully

    # Test timeout exception
    with pytest.raises(CommandTimeout):
        with timeout(1):
            time.sleep(2)  # Should timeout
