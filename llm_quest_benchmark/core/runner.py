"""Quest runner implementation with improved logging and error handling"""
from copy import deepcopy
import json
import logging
import sqlite3
import threading
import warnings
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from llm_quest_benchmark.agents.base import QuestPlayer
from llm_quest_benchmark.agents.llm_agent import LLMAgent
from llm_quest_benchmark.constants import DEFAULT_QUEST_TIMEOUT
from llm_quest_benchmark.core.logging import LogManager, QuestLogger
from llm_quest_benchmark.core.time import CommandTimeout, run_with_timeout
from llm_quest_benchmark.environments.qm import QMPlayerEnv as QuestEnvironment
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.schemas.config import AgentConfig
from llm_quest_benchmark.schemas.state import AgentState

# Configure logging
logging.getLogger('quest').setLevel(logging.WARNING)
logging.getLogger('LLMAgent').setLevel(logging.WARNING)


def run_quest_with_timeout(
        quest_path: str,
        agent: QuestPlayer,
        timeout: int = DEFAULT_QUEST_TIMEOUT,
        agent_config: Optional[AgentConfig] = None,
        debug: bool = False,
        callbacks: List[Callable[[str, Any], None]] = None) -> Optional[QuestOutcome]:
    """Run quest with timeout."""
    logger: Optional[QuestLogger] = None
    executor: Optional[ThreadPoolExecutor] = None
    try:
        # Get agent_id from agent itself if available, or from config
        agent_id = getattr(agent, 'agent_id', None)
        if agent_id is None and agent_config:
            agent_id = agent_config.agent_id

        # Initialize logger with agent_id
        logger = QuestLogger(debug=debug, agent=agent_id)
        logger.set_quest_file(quest_path)

        # Create quest environment and runner
        env = QuestEnvironment(quest_path)
        runner = QuestRunner(agent=agent,
                             debug=debug,
                             callbacks=callbacks or [],
                             quest_logger=logger,
                             agent_config=agent_config)

        # Run quest with timeout
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(runner.run, quest_path)
        try:
            outcome = future.result(timeout=max(timeout, 1))

            # Update run with agent_id and config if provided
            if agent_config and agent_id:
                try:
                    # Ensure we have a connection for this thread
                    logger._init_connection()

                    # Store agent config as JSON for better storage/retrieval
                    agent_config_json = json.dumps(agent_config.__dict__)

                    # Also store benchmark_id if provided
                    benchmark_id = getattr(agent_config, 'benchmark_id', None)

                    if benchmark_id:
                        # Include benchmark_id in the update if available
                        logger._local.cursor.execute(
                            '''
                            UPDATE runs
                            SET agent_id = ?, agent_config = ?, benchmark_id = ?
                            WHERE id = ?
                        ''', (agent_id, agent_config_json, benchmark_id, logger.current_run_id))
                        logger.logger.info(f"Updated run {logger.current_run_id} with benchmark_id {benchmark_id}")
                    else:
                        logger._local.cursor.execute(
                            '''
                            UPDATE runs
                            SET agent_id = ?, agent_config = ?
                            WHERE id = ?
                        ''', (agent_id, agent_config_json, logger.current_run_id))
                    logger._local.conn.commit()
                except sqlite3.OperationalError as e:
                    if "no such column: agent_id" in str(e):
                        logger.logger.warning(
                            "agent_id column not found in database, skipping update")
                    else:
                        raise

            # The outcome is already recorded in the QuestRunner
            return outcome
        except FuturesTimeoutError:
            future.cancel()
            runner.request_stop("timeout")
            logger.logger.warning(f"Quest timed out after {timeout} seconds")

            # Persist timeout as authoritative outcome.
            logger.set_quest_outcome(
                QuestOutcome.TIMEOUT.name,
                0.0,
                final_state=runner.snapshot_state(),
            )

            # Notify callbacks about the timeout
            if callbacks:
                for callback in callbacks:
                    try:
                        callback("timeout",
                                 {"message": f"Quest timed out after {timeout} seconds"})
                    except Exception as e:
                        logger.logger.error(f"Error in timeout callback: {e}")

            return QuestOutcome.TIMEOUT

    except Exception as e:
        if logger:
            logger.logger.error(f"Error running quest: {e}")
        if logger:
            logger.set_quest_outcome("ERROR", 0.0)
        raise
    finally:
        if executor:
            executor.shutdown(wait=False, cancel_futures=True)


class QuestRunner:
    """Manages quest execution with logging and metrics"""

    def __init__(self,
                 agent: QuestPlayer,
                 debug: bool = False,
                 callbacks: List[Callable[[str, Any], None]] = None,
                 quest_logger: QuestLogger = None,
                 agent_config = None):
        """Initialize components needed for quest execution"""
        self.agent = agent
        self.debug = debug
        self.callbacks = callbacks or []
        self.step_count = 0
        self.env = None
        self.agent_config = agent_config
        self._stop_requested = threading.Event()
        self._stop_reason = ""

        # Set up central logging
        log_manager = LogManager()
        log_manager.setup(debug=debug)
        self.logger = log_manager.get_logger()

        # Use provided quest logger or create a new one
        self.quest_logger = quest_logger
        if self.quest_logger is None:
            self.quest_logger = QuestLogger(debug=self.debug, agent=str(self.agent))

        if debug:
            self.logger.debug(f"QuestRunner initialized with agent: {str(agent)}")

    def request_stop(self, reason: str = "requested") -> None:
        """Signal runner loop to stop as soon as possible."""
        self._stop_reason = reason
        self._stop_requested.set()

    def snapshot_state(self) -> Optional[Dict[str, Any]]:
        """Best-effort snapshot of current environment state."""
        if not self.env:
            return None
        state = self.env.state if getattr(self.env, "state", None) else None
        if isinstance(state, dict):
            return deepcopy(state)
        return None

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
                if self._stop_requested.is_set():
                    self.logger.warning("Quest runner stop requested: %s", self._stop_reason or "unknown")
                    return QuestOutcome.TIMEOUT

                self.step_count += 1
                self._notify_callbacks("progress", {
                    "step": self.step_count,
                    "message": f"Processing step {self.step_count}..."
                })

                # Check if there are any choices available
                if not self.env.state['choices']:
                    if self.env and self.env.state:
                        self.agent.on_game_end(self.env.state)

                    # Log quest outcome
                    outcome = QuestOutcome.FAILURE
                    reward = self.env.state.get('reward',
                                                0.0) if self.env and self.env.state else 0.0
                    if self.quest_logger:
                        self.quest_logger.set_quest_outcome(
                            outcome.name,
                            reward,
                            final_state=self.env.state if self.env else None,
                        )

                    return outcome

                current_location_id = self.env.state['location_id']
                current_observation = observation
                current_choices = deepcopy(self.env.state['choices'])

                # Get agent's action and take step
                action = self.agent.get_action(current_observation, current_choices)

                if self.debug:
                    self.logger.debug(f"Agent selected action: {action}")
                    choices_debug = []
                    for i, c in enumerate(current_choices):
                        choices_debug.append(f"{i+1}: {c['text']}")
                    self.logger.debug(f"Available choices: {choices_debug}")

                # Validate action is within range (extra safety check)
                num_choices = len(current_choices)
                if action < 1 or action > num_choices:
                    self.logger.error(
                        f"RUNNER ERROR - Action {action} out of range 1-{num_choices}")
                    self.logger.error(f"Defaulting to action 1")
                    action = 1

                if self._stop_requested.is_set():
                    self.logger.info("Quest runner stopped before step after %s", self._stop_reason or "request")
                    return QuestOutcome.TIMEOUT

                try:
                    self.logger.debug(f"Taking step with final action: {action}")
                    observation, done, success, info = self.env.step(action)

                    # Create agent state and notify callbacks
                    agent_state = AgentState(
                        step=self.step_count,
                        location_id=current_location_id,
                        observation=current_observation,
                        choices=current_choices,
                        action=str(action),
                        llm_response=self.agent.get_last_response(),
                    )
                    self._notify_callbacks("game_state", agent_state)

                    # Log step to database
                    if self.quest_logger:
                        self.quest_logger.log_step(agent_state)

                    if done:
                        self.agent.on_game_end(self.env.state)

                        # Log quest outcome
                        outcome = QuestOutcome.SUCCESS if success else QuestOutcome.FAILURE
                        reward = self.env.state.get('reward',
                                                    0.0) if self.env and self.env.state else 0.0
                        if self.quest_logger:
                            # Get benchmark_id from the agent_config parameter if available
                            benchmark_id = None
                            if hasattr(self, 'agent_config') and self.agent_config and hasattr(self.agent_config, 'benchmark_id'):
                                benchmark_id = self.agent_config.benchmark_id
                            
                            self.quest_logger.set_quest_outcome(
                                outcome.name,
                                reward,
                                benchmark_id,
                                final_state=self.env.state if self.env else None,
                            )

                        return outcome

                except Exception as e:
                    if self._stop_requested.is_set():
                        self.logger.info("Quest runner stopped during step after %s", self._stop_reason or "request")
                        return QuestOutcome.TIMEOUT
                    self.logger.error("Error during step: %s", str(e), exc_info=True)
                    self._notify_callbacks("error", str(e))

                    # Log error outcome
                    if self.quest_logger:
                        # Get benchmark_id from the agent_config parameter if available
                        benchmark_id = None
                        if hasattr(self, 'agent_config') and self.agent_config and hasattr(self.agent_config, 'benchmark_id'):
                            benchmark_id = self.agent_config.benchmark_id
                        
                        self.quest_logger.set_quest_outcome(
                            QuestOutcome.ERROR.name,
                            0.0,
                            benchmark_id,
                            final_state=self.env.state if self.env else None,
                        )

                    raise

        except Exception as e:
            if self._stop_requested.is_set():
                self.logger.info("Quest runner stopped after %s", self._stop_reason or "request")
                return QuestOutcome.TIMEOUT
            self.logger.error("Error running quest: %s", str(e), exc_info=True)
            self._notify_callbacks("error", str(e))
            if self.env and self.env.state:
                self.agent.on_game_end(self.env.state)

            # Log error outcome
            if self.quest_logger:
                # Get benchmark_id from the agent_config parameter if available
                benchmark_id = None
                if hasattr(self, 'agent_config') and self.agent_config and hasattr(self.agent_config, 'benchmark_id'):
                    benchmark_id = self.agent_config.benchmark_id
                
                self.quest_logger.set_quest_outcome(
                    QuestOutcome.ERROR.name,
                    0.0,
                    benchmark_id,
                    final_state=self.env.state if self.env else None,
                )

            return QuestOutcome.ERROR
        finally:
            self._notify_callbacks("close")
