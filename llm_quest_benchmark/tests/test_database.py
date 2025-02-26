import os
import tempfile
import pytest
import json
from pathlib import Path
import sqlite3
from datetime import datetime
from llm_quest_benchmark.core.logging import QuestLogger
from llm_quest_benchmark.dataclasses.state import AgentState
from llm_quest_benchmark.dataclasses.response import LLMResponse

@pytest.fixture
def quest_logger():
    """Create a temporary quest logger for testing"""
    # Create a temporary database file
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    # Create logger with the temporary database
    logger = QuestLogger(db_path=db_path, debug=True)

    yield logger

    # Clean up
    logger.close()
    os.unlink(db_path)

def test_quest_logger_initialization(quest_logger):
    """Test quest logger initialization"""
    # Ensure we have a connection for this thread
    quest_logger._init_connection()

    # Check that the database was created
    assert os.path.exists(quest_logger.db_path)

    # Check that tables were created
    quest_logger._local.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = quest_logger._local.cursor.fetchall()
    table_names = [table[0] for table in tables]
    assert "runs" in table_names
    assert "steps" in table_names

def test_quest_logger_log_step(quest_logger):
    """Test logging a single step"""
    # Set up quest file
    quest_logger.set_quest_file("test_quest.qm")

    # Create agent state
    agent_state = AgentState(
        step=1,
        location_id="room1",
        observation="You are in a room",
        choices=[
            {"id": "1", "text": "Go north"},
            {"id": "2", "text": "Go south"}
        ],
        action="1",
        llm_response=LLMResponse(
            action=1,
            analysis="I should go north",
            reasoning="The north path looks safer"
        )
    )

    # Log the step
    quest_logger.log_step(agent_state)

    # Ensure we have a connection for this thread
    quest_logger._init_connection()

    # Check run was created
    quest_logger._local.cursor.execute("SELECT * FROM runs")
    run = quest_logger._local.cursor.fetchone()
    assert run is not None
    assert run[1] == "test_quest.qm"  # quest_file

    # Check step was logged - get column names first
    quest_logger._local.cursor.execute("PRAGMA table_info(steps)")
    columns = quest_logger._local.cursor.fetchall()
    column_names = [col[1] for col in columns]
    print(f"Steps table columns: {column_names}")

    # Now query the step data
    quest_logger._local.cursor.execute("SELECT * FROM steps WHERE run_id = ?", (run[0],))
    step = quest_logger._local.cursor.fetchone()
    assert step is not None

    # Get the indices for each column
    run_id_idx = column_names.index('run_id')
    step_idx = column_names.index('step')
    location_id_idx = column_names.index('location_id')
    observation_idx = column_names.index('observation')
    choices_idx = column_names.index('choices')
    action_idx = column_names.index('action')
    llm_response_idx = column_names.index('llm_response')

    # Check values using column indices
    assert step[run_id_idx] == run[0]  # run_id
    assert step[step_idx] == 1  # step number
    assert step[location_id_idx] == "room1"  # location_id
    assert step[observation_idx] == "You are in a room"  # observation
    assert "Go north" in step[choices_idx]  # choices
    assert step[action_idx] == "1"  # action
    assert "I should go north" in step[llm_response_idx]  # llm_response

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

    # Ensure we have a connection for this thread
    quest_logger._init_connection()

    # Get column names first
    quest_logger._local.cursor.execute("PRAGMA table_info(steps)")
    columns = quest_logger._local.cursor.fetchall()
    column_names = [col[1] for col in columns]

    # Get the indices for each column
    step_idx = column_names.index('step')
    action_idx = column_names.index('action')

    # Check all steps were logged
    quest_logger._local.cursor.execute("SELECT * FROM steps WHERE run_id = ? ORDER BY step", (run_id,))
    logged_steps = quest_logger._local.cursor.fetchall()
    assert len(logged_steps) == 3

    # Verify step sequence using column indices
    assert logged_steps[0][step_idx] == 1  # first step
    assert logged_steps[1][step_idx] == 2  # second step
    assert logged_steps[2][step_idx] == 3  # third step

    # Verify actions using column indices
    assert logged_steps[0][action_idx] == "1"  # first action
    assert logged_steps[1][action_idx] == "2"  # second action
    assert logged_steps[2][action_idx] == "1"  # third action