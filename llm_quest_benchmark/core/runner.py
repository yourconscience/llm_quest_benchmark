"""Quest runner implementation with improved logging and error handling"""
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
import warnings
from concurrent.futures import ThreadPoolExecutor
import sqlite3

from llm_quest_benchmark.agents.base import QuestPlayer
from llm_quest_benchmark.agents.llm_agent import LLMAgent
from llm_quest_benchmark.environments.qm import QMPlayerEnv as QuestEnvironment
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.core.logging import QuestLogger, LogManager
from llm_quest_benchmark.core.time import run_with_timeout, CommandTimeout
from llm_quest_benchmark.constants import DEFAULT_QUEST_TIMEOUT
from llm_quest_benchmark.dataclasses.state import AgentState
from llm_quest_benchmark.dataclasses.config import AgentConfig

# Configure logging
logging.getLogger('quest').setLevel(logging.WARNING)
logging.getLogger('LLMAgent').setLevel(logging.WARNING)

def run_quest_with_timeout(
    quest_path: str,
    agent: QuestPlayer,
    timeout: int = DEFAULT_QUEST_TIMEOUT,
    agent_config: Optional[AgentConfig] = None,
    debug: bool = False,
    callbacks: List[Callable[[str, Any], None]] = None
) -> Optional[QuestOutcome]:
    """Run quest with timeout."""
    try:
        # Get agent_id from agent_config if provided
        agent_id = None
        if agent_config:
            agent_id = agent_config.agent_id

        # Initialize logger with agent_id
        logger = QuestLogger(debug=debug, agent=agent_id)
        logger.set_quest_file(quest_path)

        # Create quest environment and runner
        env = QuestEnvironment(quest_path)
        runner = QuestRunner(agent=agent, debug=debug, callbacks=callbacks or [])

        # Run quest with timeout
        with ThreadPoolExecutor() as executor:
            future = executor.submit(runner.run, quest_path)
            try:
                # Use a slightly shorter timeout to ensure we can handle the result properly
                effective_timeout = max(timeout - 2, 1)  # At least 1 second
                outcome = future.result(timeout=effective_timeout)

                # Update run with agent_id and config if provided
                if agent_config and agent_id:
                    try:
                        # Ensure we have a connection for this thread
                        logger._init_connection()

                        logger._local.cursor.execute('''
                            UPDATE runs
                            SET agent_id = ?, agent_config = ?
                            WHERE id = ?
                        ''', (agent_id, str(agent_config.__dict__), logger.current_run_id))
                        logger._local.conn.commit()
                    except sqlite3.OperationalError as e:
                        if "no such column: agent_id" in str(e):
                            logger.logger.warning("agent_id column not found in database, skipping update")
                        else:
                            raise

                return outcome
            except TimeoutError:
                future.cancel()
                logger.logger.warning(f"Quest timed out after {timeout} seconds")

                # Notify callbacks about the timeout
                if callbacks:
                    for callback in callbacks:
                        try:
                            callback("timeout", {"message": f"Quest timed out after {timeout} seconds"})
                        except Exception as e:
                            logger.logger.error(f"Error in timeout callback: {e}")

                return None

    except Exception as e:
        logger.logger.error(f"Error running quest: {e}")
        raise

class QuestRunner:
    """Manages quest execution with logging and metrics"""
    def __init__(self, agent: QuestPlayer, debug: bool = False, logger: Any = None,
                 callbacks: List[Callable[[str, Any], None]] = None):
        """Initialize components needed for quest execution"""
        self.agent = agent
        self.debug = debug
        self.callbacks = callbacks or []

        self.logger = logger
        if logger is None:
            log_manager = LogManager()
            log_manager.setup(debug=debug)
            self.logger = log_manager.get_logger()

        self.step_count = 0
        self.env = None

        # Initialize quest logger
        self.quest_logger = QuestLogger(
            debug=self.debug,
            agent=str(self.agent)
        )

        if debug:
            self.logger.debug("QuestRunner initialized with agent: %s", str(agent))

    def _notify_callbacks(self, event: str, data: Any = None) -> None:
        """Notify all callbacks of an event"""
        for callback in self.callbacks:
            try:
                callback(event, data)
            except Exception as e:
                self.logger.error(f"Error in callback: {e}")

    def initialize(self, quest: str) -> None:
        """Initialize environment and logger for a new quest"""
        try:
            if self.debug:
                self.logger.debug("Initializing environment for quest: %s", quest)
            self.env = QuestEnvironment(quest, debug=self.debug)
            self.quest_logger.set_quest_file(quest)
            self.logger.info(f"Running quest {quest} with agent: {str(self.agent)}")
        except Exception as e:
            self.logger.error("Failed to initialize environment: %s", str(e), exc_info=True)
            raise

    def run(self, quest: str) -> QuestOutcome:
        """Run the quest until completion or error"""
        if not self.agent:
            self.logger.error("No agent initialized!")
            return QuestOutcome.ERROR

        try:
            # Initialize environment and notify callbacks
            self.initialize(quest)
            self._notify_callbacks("title")
            self._notify_callbacks("progress", {"step": 0, "message": "Starting quest..."})

            # Get initial state
            observation = self.env.reset()

            while True:
                self.step_count += 1
                self._notify_callbacks("progress", {
                    "step": self.step_count,
                    "message": f"Processing step {self.step_count}..."
                })

                # Check if there are any choices available
                if not self.env.state['choices']:
                    if self.env and self.env.state:
                        self.agent.on_game_end(self.env.state)
                    return QuestOutcome.FAILURE

                # Get agent's action and take step
                action = self.agent.get_action(observation, self.env.state['choices'])
                try:
                    observation, done, success, info = self.env.step(action)

                    # Create agent state and notify callbacks
                    agent_state = AgentState(
                        step=self.step_count,
                        location_id=self.env.state['location_id'],
                        observation=observation,
                        choices=self.env.state['choices'],
                        action=str(action),
                        llm_response=self.agent.get_last_response()
                    )
                    self._notify_callbacks("game_state", agent_state)

                    # Log step to database
                    if self.quest_logger:
                        self.quest_logger.log_step(agent_state)

                    if done:
                        self.agent.on_game_end(self.env.state)
                        return QuestOutcome.SUCCESS if success else QuestOutcome.FAILURE

                except Exception as e:
                    self.logger.error("Error during step: %s", str(e), exc_info=True)
                    self._notify_callbacks("error", str(e))
                    raise

        except Exception as e:
            self.logger.error("Error running quest: %s", str(e), exc_info=True)
            self._notify_callbacks("error", str(e))
            if self.env and self.env.state:
                self.agent.on_game_end(self.env.state)
            return QuestOutcome.ERROR
        finally:
            self._notify_callbacks("close")