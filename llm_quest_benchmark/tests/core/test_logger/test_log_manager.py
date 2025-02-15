"""Tests for logger module"""
import logging
import pytest
from pathlib import Path

from llm_quest_benchmark.core.logging import LogManager


def test_log_manager_initialization():
    """Test that LogManager initializes correctly"""
    log_manager = LogManager("test")
    logger = log_manager.get_logger()
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test"


def test_log_manager_debug_setup(tmp_path):
    """Test that debug logging setup works"""
    # Use temporary directory for logs
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    with pytest.MonkeyPatch.context() as mp:
        mp.chdir(tmp_path)
        log_manager = LogManager("test")
        log_manager.setup("debug")

        logger = log_manager.get_logger()
        logger.debug("Test debug message")

        # Check that log file was created
        log_files = list(log_dir.glob("llm_quest_*.log"))
        assert len(log_files) == 1
        assert log_files[0].read_text().strip().endswith("Test debug message")