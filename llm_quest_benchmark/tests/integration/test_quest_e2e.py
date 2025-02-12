"""Basic integration test for quest execution"""
import pytest
from pathlib import Path

from llm_quest_benchmark.core import QuestRunner, LogManager
from llm_quest_benchmark.constants import DEFAULT_QUEST


@pytest.mark.integration
def test_quest_initialization():
    """Test that quest runner can initialize without errors"""
    log_manager = LogManager("test")
    log_manager.setup("debug")
    runner = QuestRunner(logger=log_manager.get_logger())

    # Should initialize without errors
    runner.initialize(
        quest=str(DEFAULT_QUEST),
        model="sonnet",
        debug=True,
        metrics=True
    )

    # Basic validation
    assert runner.env is not None
    assert runner.agent is not None
    assert runner.metrics_logger is not None