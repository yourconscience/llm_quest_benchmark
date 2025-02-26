"""Unified logging module for LLM Quest Benchmark"""
import json
import logging
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
import os
import threading

from rich.logging import RichHandler
from llm_quest_benchmark.dataclasses.state import AgentState

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Constants
DEFAULT_DB_PATH = "metrics.db"
RESULTS_DIR = Path("results")

class LogManager:
    """Manages logging configuration"""
    def __init__(self):
        self.logger = logging.getLogger('llm_quest')

    def setup(self, debug: bool = False):
        """Setup logging configuration"""
        level = logging.DEBUG if debug else logging.INFO
        self.logger.setLevel(level)

        # Configure other loggers
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('httpcore').setLevel(logging.WARNING)

    def get_logger(self):
        """Get the logger"""
        return self.logger


class QuestLogger:
    """Logs quest runs to SQLite database and agent-specific directories"""
    # Thread-local storage for database connections
    _local = threading.local()

    def __init__(self, db_path: str = DEFAULT_DB_PATH, debug: bool = False, agent: Optional[str] = None):
        """Initialize the quest logger.

        Args:
            db_path: Path to SQLite database
            debug: Enable debug logging
            agent: Agent identifier
        """
        self.db_path = db_path
        self.debug = debug
        self.agent = agent
        self.current_run_id = None
        self.quest_file = None
        self.steps = []

        # Setup logger
        self.logger = logging.getLogger('quest_logger')
        self.logger.setLevel(logging.DEBUG if debug else logging.INFO)

        # Initialize connection for this thread
        self._init_connection()

    def _init_connection(self):
        """Initialize a thread-local database connection"""
        # Create a new connection for this thread if it doesn't exist
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self.logger.debug(f"Creating new SQLite connection for thread {threading.get_ident()}")
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.cursor = self._local.conn.cursor()

            # Create tables if they don't exist
            self._create_tables()

    def _create_tables(self):
        """Create database tables if they don't exist"""
        self._local.cursor.execute('''
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quest_file TEXT,
                quest_name TEXT,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                agent_id TEXT,
                agent_config TEXT,
                outcome TEXT
            )
        ''')

        self._local.cursor.execute('''
            CREATE TABLE IF NOT EXISTS steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER,
                step INTEGER,
                location_id TEXT,
                observation TEXT,
                choices TEXT,
                action TEXT,
                llm_response TEXT,
                FOREIGN KEY (run_id) REFERENCES runs (id)
            )
        ''')

        self._local.conn.commit()

    def set_quest_file(self, quest_file: str):
        """Set the quest file and create a new run record.

        Args:
            quest_file: Path to quest file
        """
        # Ensure we have a connection for this thread
        self._init_connection()

        self.quest_file = quest_file
        self.steps = []

        try:
            # Create run record with quest_file
            self._local.cursor.execute('''
                INSERT INTO runs (quest_file, start_time, agent_id)
                VALUES (?, ?, ?)
            ''', (quest_file, datetime.utcnow(), self.agent))
            self._local.conn.commit()
        except sqlite3.OperationalError as e:
            if "no such column: quest_file" in str(e):
                # Fallback for older schema without quest_file column
                self.logger.warning("quest_file column not found in database, using quest_name instead")
                self._local.cursor.execute('''
                    INSERT INTO runs (quest_name, start_time, agent_id)
                    VALUES (?, ?, ?)
                ''', (quest_file, datetime.utcnow(), self.agent))
                self._local.conn.commit()
            else:
                raise

        # Get the run ID
        self.current_run_id = self._local.cursor.lastrowid
        self.logger.debug(f"Created run record with ID: {self.current_run_id}")

    def log_step(self, agent_state: AgentState):
        """Log a step to the database and agent-specific directory.

        Args:
            agent_state: Agent state to log
        """
        # Ensure we have a connection for this thread
        self._init_connection()

        self.steps.append(agent_state)

        if self.debug:
            self.logger.debug(self.format_step_for_console(agent_state))

        try:
            # Format choices as JSON for storage
            choices_json = json.dumps(agent_state.choices)

            # Store all step data together including action and llm_response if available
            if agent_state.observation:
                llm_response_json = None
                if agent_state.llm_response is not None:
                    llm_response_json = json.dumps(agent_state.llm_response.to_dict())

                self._local.cursor.execute('''
                    INSERT INTO steps (run_id, step, location_id, observation, choices, action, llm_response)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    self.current_run_id,
                    agent_state.step,
                    agent_state.location_id,
                    agent_state.observation,
                    choices_json,
                    agent_state.action,
                    llm_response_json
                ))
                self._local.conn.commit()

                # Save to agent-specific directory if agent ID is provided
                if self.agent and self.quest_file:
                    self._save_to_agent_dir(agent_state)

        except Exception as e:
            self.logger.error(f"Error logging step: {e}")

    def _save_to_agent_dir(self, agent_state: AgentState):
        """Save step data to agent-specific directory.

        Args:
            agent_state: Agent state to save
        """
        try:
            # Create agent directory if it doesn't exist
            agent_dir = RESULTS_DIR / self.agent
            agent_dir.mkdir(parents=True, exist_ok=True)

            # Create quest directory if it doesn't exist
            quest_name = Path(self.quest_file).stem
            quest_dir = agent_dir / quest_name
            quest_dir.mkdir(exist_ok=True)

            # Create run directory if it doesn't exist
            run_dir = quest_dir / f"run_{self.current_run_id}"
            run_dir.mkdir(exist_ok=True)

            # Save step data
            step_data = {
                "step": agent_state.step,
                "location_id": agent_state.location_id,
                "observation": agent_state.observation,
                "choices": agent_state.choices,
                "action": agent_state.action,
                "llm_response": agent_state.llm_response.to_dict() if agent_state.llm_response else None
            }

            # Save to file
            step_file = run_dir / f"step_{agent_state.step}.json"
            with open(step_file, 'w') as f:
                json.dump(step_data, f, indent=2)

        except Exception as e:
            self.logger.error(f"Error saving to agent directory: {e}")

    def format_step_for_console(self, agent_state: AgentState) -> str:
        """Format step for console output.

        Args:
            agent_state: Agent state to format

        Returns:
            Formatted step string
        """
        choices_str = "\n".join([f"{i+1}. {choice['text']}" for i, choice in enumerate(agent_state.choices)])
        return f"Step {agent_state.step}:\nObservation: {agent_state.observation}\nChoices:\n{choices_str}\nAction: {agent_state.action}"

    def close(self):
        """Close the database connection for this thread"""
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
            self._local.cursor = None