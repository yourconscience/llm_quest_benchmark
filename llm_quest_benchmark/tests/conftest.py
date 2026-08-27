"""Shared test fixtures"""

import pytest

import llm_quest_benchmark.core.logging as logging_module
from llm_quest_benchmark.constants import DEFAULT_QUEST
from llm_quest_benchmark.core.logging import LogManager


@pytest.fixture(autouse=True)
def isolated_runtime_artifacts(tmp_path, monkeypatch):
    """Keep every test and spawned benchmark worker off developer artifacts."""
    db_path = tmp_path / "metrics.db"
    results_path = tmp_path / "results"
    monkeypatch.setenv(logging_module.DB_PATH_ENV_VAR, str(db_path))
    monkeypatch.setenv(logging_module.RESULTS_DIR_ENV_VAR, str(results_path))
    monkeypatch.setattr(logging_module, "DEFAULT_DB_PATH", str(db_path))
    monkeypatch.setattr(logging_module, "RESULTS_DIR", results_path)


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
