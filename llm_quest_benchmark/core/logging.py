"""Unified logging module for LLM Quest Benchmark"""
import json
import logging
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
import os

from rich.logging import RichHandler
from llm_quest_benchmark.dataclasses.state import AgentState


class LogManager:
    """Centralized logging configuration"""
    def __init__(self, name: str = "llm-quest"):
        # Set up logging with rich handler for console output only if not already configured
        if not logging.getLogger().handlers:
            logging.basicConfig(
                level="INFO",
                format="%(message)s",
                datefmt="[%X]",
                handlers=[RichHandler(rich_tracebacks=True)]
            )
        self.log = logging.getLogger(name)

        # Set transformers logging level
        os.environ["TRANSFORMERS_VERBOSITY"] = "error"

    def setup(self, debug: bool = False) -> None:
        """Configure logging based on debug mode"""
        self.log.setLevel(logging.DEBUG if debug else logging.INFO)
        if debug:
            self.log.debug("Debug logging enabled")

    def get_logger(self):
        """Get the configured logger"""
        return self.log


class QuestLogger:
    """Unified logger for quest execution and metrics"""
    def __init__(self,
                 name: str = "quest",
                 debug: bool = False,
                 agent: str = None):
        self.logger = logging.getLogger(name)
        self.debug = debug
        self.agent = agent
        self.steps: List[AgentState] = []
        self.quest_file: Optional[str] = None
        self.current_run_id: Optional[int] = None

        # Set up SQLite database path
        metrics_dir = Path("metrics")
        metrics_dir.mkdir(exist_ok=True)
        self.db_path = metrics_dir / "metrics.db"

        # Configure console output if not already configured
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter('%(message)s')
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)

        self.logger.setLevel(logging.DEBUG if debug else logging.INFO)

        # Initialize database connection
        self.init_database()

    def init_database(self):
        """Initialize database connection and tables - each instance gets its own connection"""
        # Close existing connection if any
        if hasattr(self, 'conn') and self.conn:
            try:
                self.conn.close()
            except:
                pass  # Ignore errors on close

        # Create new connection for this instance with thread safety
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.cursor = self.conn.cursor()

        # Drop existing tables to ensure clean schema
        self.cursor.execute("DROP TABLE IF EXISTS steps")
        self.cursor.execute("DROP TABLE IF EXISTS runs")

        # Create tables with all required columns
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY,
                quest_name TEXT,
                start_time TIMESTAMP,
                end_time TIMESTAMP
            )''')

        self.cursor.execute('''
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

        self.conn.commit()

    def set_quest_file(self, quest_file: str) -> None:
        """Set the quest file being run and create a new run entry"""
        # Ensure we have a fresh database connection in this thread
        self.init_database()

        self.quest_file = quest_file
        if self.debug:
            self.logger.debug(f"Running quest: {quest_file}")

        # Create a new run entry
        self.cursor.execute('''
            INSERT INTO runs (quest_name, start_time)
            VALUES (?, ?)
        ''', (quest_file, datetime.now().isoformat()))
        self.conn.commit()
        self.current_run_id = self.cursor.lastrowid

    def log_step(self, agent_state: AgentState) -> None:
        """Log a quest step to SQLite database"""
        if not self.current_run_id:
            raise ValueError("Quest file not set. Call set_quest_file first.")

        self.steps.append(agent_state)

        # Log into console if debug is enabled
        if self.debug:
            self.logger.debug(self.format_step_for_console(agent_state))

        # Format choices and LLM response as JSON for storage
        choices_json = json.dumps(agent_state.choices)
        llm_response_json = json.dumps(agent_state.llm_response.to_dict())

        try:
            self.cursor.execute('''
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
            self.conn.commit()
        except sqlite3.OperationalError as e:
            if "no such column" in str(e):
                # Reinitialize database with correct schema
                self.init_database()
                # Retry the insert
                self.cursor.execute('''
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
                self.conn.commit()
            else:
                raise

    def get_log_entries(self) -> List[Dict[str, Any]]:
        """Get all logged steps for the current run"""
        if not self.current_run_id:
            return []

        entries = []
        try:
            self.cursor.execute('''
                SELECT step, location_id, observation, choices, action, llm_response
                FROM steps
                WHERE run_id = ?
                ORDER BY step
            ''', (self.current_run_id,))

            for row in self.cursor.fetchall():
                entry = {
                    'step': row[0],
                    'location_id': row[1],
                    'observation': row[2],
                    'choices': json.loads(row[3]) if row[3] else [],
                    'action': row[4],
                    'llm_response': json.loads(row[5]) if row[5] else None
                }
                entries.append(entry)

        except sqlite3.OperationalError:
            self.logger.error("Failed to retrieve log entries - schema may be outdated")

        return entries

    def format_step_for_console(self, step: AgentState) -> str:
        """Format step for console output"""
        lines = [
            f"\nStep {step.step}",
            f"\nObservation:\n{step.observation}",
            f"\nChoices:",
        ]

        # Format choices as numbered list
        for i, choice in enumerate(step.choices, 1):
            lines.append(f"{i}. {choice['text']}")

        # Add action
        lines.append(f"\nAction: {step.action}")

        # Add LLM response if available
        response = step.llm_response
        if response:
            if response.analysis:
                lines.append(f"\nAnalysis: {response.analysis}")
            if response.reasoning:
                lines.append(f"\nReasoning: {response.reasoning}")

        return "\n".join(lines)

    def __del__(self):
        """Close database connection on cleanup"""
        if hasattr(self, 'conn'):
            try:
                # Update end time for the run
                if self.current_run_id:
                    self.cursor.execute('''
                        UPDATE runs SET end_time = ? WHERE id = ?
                    ''', (datetime.now().isoformat(), self.current_run_id))
                    self.conn.commit()
                self.conn.close()
            except Exception as e:
                # Log but don't raise during cleanup
                if hasattr(self, 'logger'):
                    self.logger.error(f"Error during cleanup: {e}")