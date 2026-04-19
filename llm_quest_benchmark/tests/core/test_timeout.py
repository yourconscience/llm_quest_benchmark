"""Tests for time module"""

import time

import pytest

from llm_quest_benchmark.core.time import CommandTimeout, timeout


def test_timeout_context_manager():
    """Test that timeout context manager works"""
    # Test successful completion within timeout
    with timeout(1):
        time.sleep(0.1)  # Should complete successfully

    # Test timeout exception
    with pytest.raises(CommandTimeout), timeout(1):
        time.sleep(2)  # Should timeout
