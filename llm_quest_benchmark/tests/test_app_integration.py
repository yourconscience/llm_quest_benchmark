import pytest
from llm_quest_benchmark.web.app import main
from streamlit.testing.v1 import AppTest
from llm_quest_benchmark.constants import (
    DEFAULT_TEMPLATE,
    DEFAULT_QUEST_TIMEOUT,
)
import tempfile
import json
import sqlite3
from datetime import datetime
from pathlib import Path

@pytest.fixture
def app():
    """Fixture to create and run the app"""
    at = AppTest.from_file("llm_quest_benchmark/web/app.py")
    at.run()
    return at

def test_main_app_smoke(app):
    """Basic smoke test for the main app"""
    assert not app.exception
    assert "LLM Quest Benchmark" in app.title[0].value

def test_navigation_exists(app):
    """Test navigation components exist"""
    assert "Navigation" in app.sidebar.title[0].value
    assert len(app.sidebar.radio) > 0

def test_quest_runner_basic(app):
    """Test basic quest runner components exist"""
    # Check essential components
    assert any("Quest Runner" in h.value for h in app.header)
    assert any("Run Quest" in b.label for b in app.button)

def test_benchmark_basic(app):
    """Test basic benchmark components exist"""
    # Check essential components
    buttons = [b.label for b in app.button]
    assert any("Run Quest" in label for label in buttons), "Run Quest button not found"

@pytest.fixture
def test_db():
    """Fixture to create a test database with sample data"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as db_file:
        conn = sqlite3.connect(db_file.name)
        cursor = conn.cursor()

        # Create schema
        cursor.execute('''
            CREATE TABLE runs (
                id INTEGER PRIMARY KEY,
                quest_name TEXT,
                start_time TIMESTAMP,
                end_time TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE steps (
                run_id INTEGER,
                step INTEGER,
                location_id TEXT,
                observation TEXT,
                choices TEXT,
                action TEXT,
                llm_response TEXT,
                FOREIGN KEY(run_id) REFERENCES runs(id)
            )
        ''')

        # Insert sample data
        cursor.execute(
            "INSERT INTO runs (id, quest_name, start_time) VALUES (?, ?, ?)",
            (1, "test.qm", datetime.now().isoformat())
        )

        test_response = {
            "model": "claude-3-5-sonnet",
            "outcome": "SUCCESS",
            "thought": "Test thought"
        }
        cursor.execute(
            "INSERT INTO steps (run_id, step, location_id, observation, choices, action, llm_response) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (1, 1, "start", "Test observation", json.dumps([{"text": "Choice 1"}]), "Choice 1", json.dumps(test_response))
        )

        conn.commit()
        conn.close()

        yield db_file.name
        Path(db_file.name).unlink(missing_ok=True)

def test_analyze_basic(app, test_db):
    """Test basic analyze components exist"""
    assert any("Quest" in h.value for h in app.header)