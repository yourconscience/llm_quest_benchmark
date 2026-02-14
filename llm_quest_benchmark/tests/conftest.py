"""Shared test fixtures"""
import pytest
from pathlib import Path

from llm_quest_benchmark.core.logging import LogManager
from llm_quest_benchmark.constants import DEFAULT_QUEST


@pytest.fixture
def test_logger():
    """Get a test logger"""
    log_manager = LogManager("test")
    log_manager.setup("debug")
    return log_manager.get_logger()


@pytest.fixture
def example_quest_path():
    """Get path to test quest file"""
    return DEFAULT_QUEST


@pytest.fixture
def example_observation():
    """Example quest observation"""
    return """You are at a trading station.

Available actions:
1. Talk to merchant
2. Leave station
"""
