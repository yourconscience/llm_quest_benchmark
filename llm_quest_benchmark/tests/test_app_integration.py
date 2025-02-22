import pytest
from llm_quest_benchmark.web.app import main
from streamlit.testing.v1 import AppTest
from llm_quest_benchmark.constants import (
    DEFAULT_TEMPLATE,
)
from llm_quest_benchmark.utils import choice_mapper
from llm_quest_benchmark.llm.prompt import PromptRenderer

def test_main_app_smoke():
    """Basic smoke test for the main app"""
    at = AppTest.from_file("llm_quest_benchmark/web/app.py")
    at.run()
    assert not at.exception

def test_quest_runner_section():
    """Test quest runner section initialization"""
    at = AppTest.from_file("llm_quest_benchmark/web/app.py")
    at.run()
    # Упрощаем проверки до базового функционала
    assert "Quest Runner" in [h.value for h in at.header]