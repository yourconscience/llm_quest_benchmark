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
from llm_quest_benchmark.schemas import AgentState

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
    
    @staticmethod
    def _safe_json_load(json_str, default=None):
        """Safely load JSON with error handling and repair attempts"""
        if not json_str:
            return default
            
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Try to repair damaged JSON
            try:
                from json_repair import repair_json
                repaired = repair_json(json_str)
                return json.loads(repaired)
            except ImportError:
                # Log warning about missing json-repair
                import logging
                logging.getLogger('quest_logger').warning("json-repair module not available - some JSON may not parse correctly")
                
                # Manual repair attempt
                try:
                    # If it starts with a string that looks like a dict
                    if json_str.strip().startswith('{'):
                        # Extract everything between the first { and the last }
                        clean_str = json_str[json_str.find('{'):json_str.rfind('}')+1]
                        return json.loads(clean_str)
                except:
                    pass
            
            # Return default if all repair attempts failed
            return default

    @staticmethod
    def _safe_int(value) -> Optional[int]:
        """Best-effort conversion to int."""
        try:
            if value is None:
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _choices_map(choices: List[Dict[str, Any]]) -> Dict[str, str]:
        """Map quest choices to a compact indexed text dictionary."""
        return {str(idx): choice.get("text", "") for idx, choice in enumerate(choices, start=1)}

    @staticmethod
    def _selected_choice_map(
        choices_map: Dict[str, str], action_index: Optional[int]
    ) -> Optional[Dict[str, str]]:
        """Return selected choice as {index: text} if action is valid."""
        if action_index is None:
            return None
        key = str(action_index)
        if key not in choices_map:
            return None
        return {key: choices_map[key]}

    def _format_step_export(
        self,
        step_num: int,
        location_id: str,
        observation: str,
        choices: List[Dict[str, Any]],
        action: Any,
        llm_response: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Format an exported step in compact analysis-friendly form."""
        del location_id  # Not needed in exported run summaries.
        choices_map = self._choices_map(choices)
        parsed_action_index = self._safe_int(action)
        analysis = None
        reasoning = None
        is_default = True
        parse_mode = None
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        estimated_cost_usd = None

        if isinstance(llm_response, dict):
            parsed_action_index = self._safe_int(
                llm_response.get("action")
                or llm_response.get("result")
                or llm_response.get("choice")
                or action
            )
            analysis = llm_response.get("analysis")
            reasoning = llm_response.get("reasoning")
            is_default = bool(llm_response.get("is_default", False))
            parse_mode = llm_response.get("parse_mode")
            prompt_tokens = int(llm_response.get("prompt_tokens") or 0)
            completion_tokens = int(llm_response.get("completion_tokens") or 0)
            total_tokens = int(
                llm_response.get("total_tokens")
                or (prompt_tokens + completion_tokens)
            )
            if llm_response.get("estimated_cost_usd") is not None:
                estimated_cost_usd = float(llm_response.get("estimated_cost_usd"))

        llm_decision = {
            "analysis": analysis,
            "reasoning": reasoning,
            "is_default": is_default,
            "parse_mode": parse_mode,
            "choice": self._selected_choice_map(choices_map, parsed_action_index),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": estimated_cost_usd,
        }

        return {
            "step": step_num,
            "observation": observation,
            "choices": choices_map,
            "llm_decision": llm_decision,
        }
    # Thread-local storage for database connections
    _local = threading.local()
    # Track all instances for cleanup
    _instances = []

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
        self.final_state = None

        # Setup logger
        self.logger = logging.getLogger('quest_logger')
        self.logger.setLevel(logging.DEBUG if debug else logging.INFO)

        # Initialize connection for this thread
        self._init_connection()
        
        # Add this instance to the list of all instances
        QuestLogger._instances.append(self)
        
        # Setup exit handler if this is the first instance
        if len(QuestLogger._instances) == 1:
            import atexit
            import signal
            is_pytest = bool(os.getenv("PYTEST_CURRENT_TEST"))
            
            # Define shutdown handler
            def _shutdown_handler(signal=None, frame=None):
                self.logger.info("Shutting down gracefully - closing database connections")
                for instance in QuestLogger._instances:
                    instance.close()
                QuestLogger._instances.clear()
            
            if not is_pytest:
                # Register shutdown handlers
                atexit.register(_shutdown_handler)
                
                # Only register signal handlers in the main thread
                if threading.current_thread() is threading.main_thread():
                    try:
                        signal.signal(signal.SIGINT, _shutdown_handler)
                        signal.signal(signal.SIGTERM, _shutdown_handler)
                    except ValueError:
                        # Signal handlers can only be set in the main thread
                        self.logger.debug("Skipping signal handlers in non-main thread")

    def _init_connection(self):
        """Initialize a thread-local database connection"""
        # Create a new connection for this thread if it doesn't exist
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            # Reducing debug logging
            pass  # Skip thread connection logging
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
            if 'benchmark_id' not in columns:
                self._local.cursor.execute("ALTER TABLE runs ADD COLUMN benchmark_id TEXT")
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
                    run_duration REAL,
                    benchmark_id TEXT
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
        # Skip logging run record ID to reduce output
        pass

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
            choices_json = json.dumps(agent_state.choices, ensure_ascii=False)

            # Store all step data together including action and llm_response if available
            if agent_state.observation:
                llm_response_json = None
                if agent_state.llm_response is not None:
                    llm_response_json = json.dumps(
                        agent_state.llm_response.to_dict(),
                        ensure_ascii=False,
                    )

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

    def set_quest_outcome(
        self,
        outcome: str,
        reward: float = 0.0,
        benchmark_id: str = None,
        final_state: Optional[Dict[str, Any]] = None,
    ):
        """Set the quest outcome and finalize the run.

        Args:
            outcome: Quest outcome (SUCCESS, FAILURE, etc.)
            reward: Final reward value
            benchmark_id: Optional benchmark ID to associate with this run
            final_state: Optional final environment state snapshot for export
        """
        if not self.current_run_id:
            self.logger.warning("Cannot set outcome, no active run")
            return

        self.run_outcome = outcome
        self.final_state = final_state
        self.end_time = datetime.utcnow()
        run_duration = (self.end_time - self.start_time).total_seconds()

        try:
            # Update the run record with outcome and end time
            if benchmark_id:
                self.logger.debug(f"Setting quest outcome with benchmark_id: {benchmark_id}")
                self._local.cursor.execute('''
                    UPDATE runs 
                    SET outcome = ?, end_time = ?, reward = ?, run_duration = ?, benchmark_id = ?
                    WHERE id = ?
                ''', (outcome, self.end_time, reward, run_duration, benchmark_id, self.current_run_id))
            else:
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
        """Export the complete run to a single run_summary.json file."""
        if not self.agent or not self.quest_file or not self.current_run_id:
            return
        if self.agent.startswith("random"):
            # Keep random-agent runs in DB for diagnostics, but avoid result-dir clutter.
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
            
            # Save complete run summary
            run_summary_file = run_dir / "run_summary.json"
            with open(run_summary_file, 'w', encoding='utf-8') as f:
                json.dump(run_data, f, indent=2, ensure_ascii=False)

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
                   agent_config, outcome, reward, run_duration, benchmark_id
            FROM runs
            WHERE id = ?
        ''', (self.current_run_id,))
        
        run = self._local.cursor.fetchone()
        if not run:
            return {"error": f"Run with ID {self.current_run_id} not found"}
            
        quest_file, quest_name, start_time, end_time, agent_id, agent_config, outcome, reward, run_duration, benchmark_id = run
        
        # Get steps for this run
        self._local.cursor.execute('''
            SELECT step, location_id, observation, choices, action, llm_response
            FROM steps
            WHERE run_id = ?
            ORDER BY step
        ''', (self.current_run_id,))
        
        steps = []
        usage_prompt_tokens = 0
        usage_completion_tokens = 0
        usage_total_tokens = 0
        usage_estimated_cost = 0.0
        usage_priced_steps = 0
        for step_data in self._local.cursor.fetchall():
            step_num, location_id, obs, choices_json, action, llm_response = step_data
            parsed_choices = self._safe_json_load(choices_json, [])
            parsed_response = self._safe_json_load(llm_response)
            if isinstance(parsed_response, dict):
                prompt_tokens = int(parsed_response.get("prompt_tokens") or 0)
                completion_tokens = int(parsed_response.get("completion_tokens") or 0)
                total_tokens = int(
                    parsed_response.get("total_tokens")
                    or (prompt_tokens + completion_tokens)
                )
                usage_prompt_tokens += prompt_tokens
                usage_completion_tokens += completion_tokens
                usage_total_tokens += total_tokens
                if parsed_response.get("estimated_cost_usd") is not None:
                    usage_estimated_cost += float(parsed_response.get("estimated_cost_usd"))
                    usage_priced_steps += 1
            steps.append(
                self._format_step_export(
                    step_num=step_num,
                    location_id=location_id,
                    observation=obs,
                    choices=parsed_choices if isinstance(parsed_choices, list) else [],
                    action=action,
                    llm_response=parsed_response if isinstance(parsed_response, dict) else None,
                )
            )
        
        return {
            "run_id": self.current_run_id,
            "quest_file": quest_file,
            "quest_name": quest_name,
            "start_time": start_time,
            "end_time": end_time,
            "agent_id": agent_id,
            "agent_config": self._safe_json_load(agent_config),
            "outcome": outcome,
            "reward": reward,
            "run_duration": run_duration,
            "benchmark_id": benchmark_id,
            "final_state": self.final_state,
            "usage": {
                "prompt_tokens": usage_prompt_tokens,
                "completion_tokens": usage_completion_tokens,
                "total_tokens": usage_total_tokens,
                "estimated_cost_usd": (
                    round(usage_estimated_cost, 8) if usage_priced_steps > 0 else None
                ),
                "priced_steps": usage_priced_steps,
            },
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
