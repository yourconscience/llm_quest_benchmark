"""Unified logging module for LLM Quest Benchmark"""
import json
import logging
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
import os

from rich.logging import RichHandler
from llm_quest_benchmark.dataclasses.logging import QuestStep


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
        self.steps: List[QuestStep] = []
        self.quest_file: Optional[str] = None
        self.current_run_id: Optional[int] = None

        # Set up SQLite database
        metrics_dir = Path("metrics")
        metrics_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        db_path = metrics_dir / "metrics.db"
        self.conn = sqlite3.connect(str(db_path))
        self.cursor = self.conn.cursor()

        # Create tables if they don't exist
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
                observation TEXT,
                choices TEXT,
                action INTEGER,
                reward REAL,
                FOREIGN KEY(run_id) REFERENCES runs(id)
            )''')
        self.conn.commit()

        # Configure console output if not already configured
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter('%(message)s')
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)

        self.logger.setLevel(logging.DEBUG if debug else logging.INFO)

    def set_quest_file(self, quest_file: str) -> None:
        """Set the quest file being run and create a new run entry"""
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

    def log_step(self,
                 step: int,
                 state: str,
                 choices: list,
                 response: str,
                 reward: float = 0.0,
                 metrics: Dict[str, Any] = None,
                 llm_response: Optional[Dict[str, Any]] = None) -> None:
        """Log a quest step to SQLite database"""
        if not self.current_run_id:
            raise ValueError("Quest file not set. Call set_quest_file first.")

        quest_step = QuestStep(
            step=step,
            state=state,
            choices=choices,
            response=response,
            reward=reward,
            metrics=metrics,
            llm_response=llm_response
        )
        self.steps.append(quest_step)

        # Log into console if debug is enabled
        self.logger.debug(quest_step.to_console_line())

        # Convert choices to JSON string for storage
        choices_json = json.dumps(choices, ensure_ascii=False)

        # Store step in SQLite
        try:
            action = int(response)  # Convert response to integer for storage
        except (ValueError, TypeError):
            action = 0  # Default value if conversion fails

        self.cursor.execute('''
            INSERT INTO steps (run_id, step, observation, choices, action, reward)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (self.current_run_id, step, state, choices_json, action, reward))
        self.conn.commit()

        # Debug logging if enabled
        if self.debug:
            self.logger.debug(f"Step {step} details:")
            self.logger.debug(f"State: {state[:200]}...")
            self.logger.debug(f"Response: {response}")
            self.logger.debug(f"Reward: {reward}")

    def __del__(self):
        """Close database connection on cleanup"""
        if hasattr(self, 'conn'):
            # Update end time for the run
            if self.current_run_id:
                self.cursor.execute('''
                    UPDATE runs SET end_time = ? WHERE id = ?
                ''', (datetime.now().isoformat(), self.current_run_id))
                self.conn.commit()
            self.conn.close()