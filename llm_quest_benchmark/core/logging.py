"""Unified logging module for LLM Quest Benchmark"""
import json
import logging
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
import os
import threading

from rich.logging import RichHandler
from llm_quest_benchmark.dataclasses import AgentState

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
    """Logs quest runs to SQLite database and exports to JSON when complete"""
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
        self.run_outcome = None
        self.end_time = None

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
        # Check if the runs table already exists
        self._local.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='runs'")
        table_exists = self._local.cursor.fetchone() is not None
        
        if table_exists:
            # Check if we need to add columns to existing table
            self._local.cursor.execute("PRAGMA table_info(runs)")
            columns = [column[1] for column in self._local.cursor.fetchall()]
            
            # Add missing columns
            if 'outcome' not in columns:
                self._local.cursor.execute("ALTER TABLE runs ADD COLUMN outcome TEXT")
            if 'reward' not in columns:
                self._local.cursor.execute("ALTER TABLE runs ADD COLUMN reward REAL")
            if 'run_duration' not in columns:
                self._local.cursor.execute("ALTER TABLE runs ADD COLUMN run_duration REAL")
        else:
            # Create the runs table if it doesn't exist
            self._local.cursor.execute('''
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    quest_file TEXT,
                    quest_name TEXT,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    agent_id TEXT,
                    agent_config TEXT,
                    outcome TEXT,
                    reward REAL,
                    run_duration REAL
                )
            ''')

        # Create steps table
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
        self.start_time = datetime.utcnow()

        try:
            # Extract quest name from path (filename without extension)
            quest_name = Path(quest_file).stem

            # Create run record with both quest_file and quest_name
            self._local.cursor.execute('''
                INSERT INTO runs (quest_file, quest_name, start_time, agent_id)
                VALUES (?, ?, ?, ?)
            ''', (quest_file, quest_name, self.start_time, self.agent))
            self._local.conn.commit()
        except sqlite3.OperationalError as e:
            if "no such column: quest_file" in str(e):
                # Fallback for older schema without quest_file column
                self.logger.warning("quest_file column not found in database, using quest_name instead")

                # Extract quest name from path (filename without extension)
                quest_name = Path(quest_file).stem

                self._local.cursor.execute('''
                    INSERT INTO runs (quest_name, start_time, agent_id)
                    VALUES (?, ?, ?)
                ''', (quest_name, self.start_time, self.agent))
                self._local.conn.commit()
            else:
                raise

        # Get the run ID
        self.current_run_id = self._local.cursor.lastrowid
        self.logger.debug(f"Created run record with ID: {self.current_run_id}")

    def log_step(self, agent_state: AgentState):
        """Log a step to the database.

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

        except Exception as e:
            self.logger.error(f"Error logging step: {e}")

    def set_quest_outcome(self, outcome: str, reward: float = 0.0):
        """Set the quest outcome and finalize the run.

        Args:
            outcome: Quest outcome (SUCCESS, FAILURE, etc.)
            reward: Final reward value
        """
        if not self.current_run_id:
            self.logger.warning("Cannot set outcome, no active run")
            return

        self.run_outcome = outcome
        self.end_time = datetime.utcnow()
        run_duration = (self.end_time - self.start_time).total_seconds()

        try:
            # Update the run record with outcome and end time
            self._local.cursor.execute('''
                UPDATE runs 
                SET outcome = ?, end_time = ?, reward = ?, run_duration = ?
                WHERE id = ?
            ''', (outcome, self.end_time, reward, run_duration, self.current_run_id))
            self._local.conn.commit()

            # Export the run to JSON
            self._export_run_to_json()

        except Exception as e:
            self.logger.error(f"Error setting quest outcome: {e}")

    def _export_run_to_json(self):
        """Export the complete run to JSON files.
        Creates both individual step files and a full run summary file.
        """
        if not self.agent or not self.quest_file or not self.current_run_id:
            return

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

            # Fetch complete run data from database
            run_data = self._get_run_data()
            
            # Save individual step files
            for step in run_data["steps"]:
                step_file = run_dir / f"step_{step['step']}.json"
                with open(step_file, 'w') as f:
                    json.dump(step, f, indent=2)

            # Save complete run summary
            run_summary_file = run_dir / "run_summary.json"
            with open(run_summary_file, 'w') as f:
                json.dump(run_data, f, indent=2)

            self.logger.debug(f"Exported run data to {run_summary_file}")

        except Exception as e:
            self.logger.error(f"Error exporting run to JSON: {e}")

    def _get_run_data(self) -> Dict[str, Any]:
        """Get complete run data from the database for the current run.
        
        Returns:
            Dict containing run and step data
        """
        # Ensure we have a connection for this thread
        self._init_connection()
        
        # Get run data
        self._local.cursor.execute('''
            SELECT quest_file, quest_name, start_time, end_time, agent_id, 
                   agent_config, outcome, reward, run_duration
            FROM runs
            WHERE id = ?
        ''', (self.current_run_id,))
        
        run = self._local.cursor.fetchone()
        if not run:
            return {"error": f"Run with ID {self.current_run_id} not found"}
            
        quest_file, quest_name, start_time, end_time, agent_id, agent_config, outcome, reward, run_duration = run
        
        # Get steps for this run
        self._local.cursor.execute('''
            SELECT step, location_id, observation, choices, action, llm_response
            FROM steps
            WHERE run_id = ?
            ORDER BY step
        ''', (self.current_run_id,))
        
        steps = []
        for step_data in self._local.cursor.fetchall():
            step_num, location_id, obs, choices_json, action, llm_response = step_data
            steps.append({
                "step": step_num,
                "location_id": location_id,
                "observation": obs,
                "choices": json.loads(choices_json) if choices_json else [],
                "action": action,
                "llm_response": json.loads(llm_response) if llm_response else None
            })
        
        return {
            "run_id": self.current_run_id,
            "quest_file": quest_file,
            "quest_name": quest_name,
            "start_time": start_time,
            "end_time": end_time,
            "agent_id": agent_id,
            "agent_config": json.loads(agent_config) if agent_config else None,
            "outcome": outcome,
            "reward": reward,
            "run_duration": run_duration,
            "steps": steps
        }

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