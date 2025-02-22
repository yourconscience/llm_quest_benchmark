import pytest
from llm_quest_benchmark.web.app import main
from streamlit.testing.v1 import AppTest

def test_main_app_smoke():
    """Basic smoke test for the main app"""
    at = AppTest.from_file("llm_quest_benchmark/web/app.py")
    at.run()
    assert not at.exception

def test_quest_runner_section():
    """Test quest runner section initialization"""
    at = AppTest.from_file("llm_quest_benchmark/web/app.py")
    at.run()
    at.sidebar.radio("Navigation").set_value("Quest Runner").run()
    assert at.header[0].value == "Quest Runner" 