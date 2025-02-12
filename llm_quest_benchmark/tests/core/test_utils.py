"""Tests for core utilities"""
import logging
import pytest
import time
from pathlib import Path

from llm_quest_benchmark.core.utils import LogManager, timeout, CommandTimeout


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


def test_timeout_context_manager():
    """Test that timeout context manager works"""
    # Test successful completion within timeout
    with timeout(1):
        time.sleep(0.1)  # Should complete successfully

    # Test timeout exception
    with pytest.raises(CommandTimeout):
        with timeout(1):
            time.sleep(2)  # Should timeout