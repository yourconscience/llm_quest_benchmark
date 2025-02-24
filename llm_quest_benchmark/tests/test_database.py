import os
import sqlite3
import pytest
from datetime import datetime
from llm_quest_benchmark.core.logging import QuestLogger
from llm_quest_benchmark.dataclasses.state import AgentState
from llm_quest_benchmark.dataclasses.response import LLMResponse

@pytest.fixture
def quest_logger():
    # Use in-memory SQLite for testing
    logger = QuestLogger(name="test_quest", debug=True)
    logger.conn = sqlite3.connect(':memory:')
    logger.cursor = logger.conn.cursor()

    # Create tables
    logger.cursor.execute('''
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY,
            quest_name TEXT,
            start_time TIMESTAMP,
            end_time TIMESTAMP
        )''')
    logger.cursor.execute('''
        CREATE TABLE IF NOT EXISTS steps (
            run_id INTEGER,
            step INTEGER,
            location_id TEXT,
            observation TEXT,
            choices TEXT,
            action TEXT,
            llm_response TEXT,
            FOREIGN KEY(run_id) REFERENCES runs(id)
        )''')
    return logger

def test_quest_logger_initialization(quest_logger):
    """Test that QuestLogger initializes correctly with SQLite"""
    assert quest_logger.conn is not None
    assert quest_logger.cursor is not None

    # Check tables exist
    cursor = quest_logger.cursor
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    assert 'runs' in tables
    assert 'steps' in tables

def test_quest_logger_log_step(quest_logger):
    """Test logging a quest step to SQLite"""
    # Set up quest file
    quest_logger.set_quest_file("test_quest.qm")

    # Create agent state
    agent_state = AgentState(
        step=1,
        location_id="room1",
        observation="You are in a room",
        choices=[{"id": "1", "text": "Go north"}, {"id": "2", "text": "Go south"}],
        action="1",
        llm_response=LLMResponse(
            action=1,
            analysis="I should go north",
            reasoning="The north path looks safer"
        )
    )

    # Log the step
    quest_logger.log_step(agent_state)

    # Check run was created
    cursor = quest_logger.cursor
    cursor.execute("SELECT * FROM runs")
    run = cursor.fetchone()
    assert run is not None
    assert run[1] == "test_quest.qm"  # quest_name

    # Check step was logged
    cursor.execute("SELECT * FROM steps WHERE run_id = ?", (run[0],))
    step = cursor.fetchone()
    assert step is not None
    assert step[1] == 1  # step number
    assert step[2] == "room1"  # location_id
    assert step[3] == "You are in a room"  # observation
    assert "Go north" in step[4]  # choices
    assert step[5] == "1"  # action
    assert "I should go north" in step[6]  # llm_response

def test_quest_logger_multiple_steps(quest_logger):
    """Test logging multiple steps in sequence"""
    # Set up quest file once at the beginning
    quest_logger.set_quest_file("test_quest.qm")
    run_id = quest_logger.current_run_id

    # Create and log multiple steps
    steps = [
        AgentState(
            step=1,
            location_id="room1",
            observation="Room 1",
            choices=[{"id": "1", "text": "North"}, {"id": "2", "text": "South"}],
            action="1",
            llm_response=LLMResponse(action=1)
        ),
        AgentState(
            step=2,
            location_id="room2",
            observation="Room 2",
            choices=[{"id": "1", "text": "East"}, {"id": "2", "text": "West"}],
            action="2",
            llm_response=LLMResponse(action=2)
        ),
        AgentState(
            step=3,
            location_id="room3",
            observation="Room 3",
            choices=[{"id": "1", "text": "Up"}, {"id": "2", "text": "Down"}],
            action="1",
            llm_response=LLMResponse(action=1)
        )
    ]

    for step in steps:
        quest_logger.log_step(step)

    # Check all steps were logged
    cursor = quest_logger.cursor
    cursor.execute("SELECT * FROM steps WHERE run_id = ? ORDER BY step", (run_id,))
    logged_steps = cursor.fetchall()
    assert len(logged_steps) == 3

    # Verify step sequence
    assert logged_steps[0][1] == 1  # first step
    assert logged_steps[1][1] == 2  # second step
    assert logged_steps[2][1] == 3  # third step

    # Verify actions
    assert logged_steps[0][5] == "1"  # first action
    assert logged_steps[1][5] == "2"  # second action
    assert logged_steps[2][5] == "1"  # third action