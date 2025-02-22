import os
import sqlite3
import pytest
from datetime import datetime
from llm_quest_benchmark.core.logging import QuestLogger
from llm_quest_benchmark.dataclasses.logging import QuestStep

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
            observation TEXT,
            choices TEXT,
            action INTEGER,
            reward REAL,
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

    # Log a step
    quest_logger.log_step(
        step=1,
        state="You are in a room",
        choices=["Go north", "Go south"],
        response="1",
        reward=0.5,
        metrics={"time": 1.0},
        llm_response={"reasoning": "I chose north"}
    )

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
    assert step[2] == "You are in a room"  # observation
    assert "Go north" in step[3]  # choices
    assert step[4] == 1  # action
    assert step[5] == 0.5  # reward

def test_quest_logger_multiple_steps(quest_logger):
    """Test logging multiple steps in sequence"""
    quest_logger.set_quest_file("test_quest.qm")

    # Log multiple steps
    steps = [
        (1, "Room 1", ["North", "South"], "1", 0.0),
        (2, "Room 2", ["East", "West"], "2", 0.5),
        (3, "Room 3", ["Up", "Down"], "1", 1.0),
    ]

    for step_num, state, choices, response, reward in steps:
        quest_logger.log_step(
            step=step_num,
            state=state,
            choices=choices,
            response=response,
            reward=reward
        )

    # Check all steps were logged
    cursor = quest_logger.cursor
    cursor.execute("SELECT * FROM steps ORDER BY step")
    logged_steps = cursor.fetchall()
    assert len(logged_steps) == 3

    # Verify step sequence
    assert logged_steps[0][1] == 1  # first step
    assert logged_steps[1][1] == 2  # second step
    assert logged_steps[2][1] == 3  # third step

    # Verify rewards
    assert logged_steps[0][5] == 0.0  # first reward
    assert logged_steps[1][5] == 0.5  # second reward
    assert logged_steps[2][5] == 1.0  # third reward