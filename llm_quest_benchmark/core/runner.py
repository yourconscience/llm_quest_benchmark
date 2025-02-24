"""Quest runner implementation with improved logging and error handling"""
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
import warnings
from concurrent.futures import ThreadPoolExecutor

from llm_quest_benchmark.agents.base import QuestPlayer
from llm_quest_benchmark.agents.llm_agent import LLMAgent
from llm_quest_benchmark.environments.qm import QMPlayerEnv as QuestEnvironment
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.core.logging import QuestLogger, LogManager
from llm_quest_benchmark.core.time import run_with_timeout, CommandTimeout
from llm_quest_benchmark.constants import DEFAULT_LANG, DEFAULT_QUEST_TIMEOUT
from llm_quest_benchmark.renderers.terminal import RichRenderer
from llm_quest_benchmark.renderers.null import NoRenderer
from llm_quest_benchmark.renderers.base import BaseRenderer
from llm_quest_benchmark.dataclasses.state import AgentState

# Configure logging
logging.getLogger('quest').setLevel(logging.WARNING)
logging.getLogger('LLMAgent').setLevel(logging.WARNING)

def run_quest_with_timeout(
    quest_path: str,
    agent: QuestPlayer,
    timeout: int = DEFAULT_QUEST_TIMEOUT,
    agent_id: Optional[str] = None,
    agent_config: Optional[str] = None,
    debug: bool = False,
    callbacks: List[Callable[[str, Any], None]] = None
) -> Optional[QuestOutcome]:
    """Run quest with timeout.

    Args:
        quest_path: Path to quest file
        agent: Quest player agent
        timeout: Timeout in seconds
        agent_id: Optional unique identifier for the agent
        agent_config: Optional JSON string containing agent configuration
        debug: Enable debug logging and output
        callbacks: Optional list of callback functions for progress updates

    Returns:
        QuestOutcome if quest completed, None if timed out
    """
    try:
        # Initialize logger with agent_id
        logger = QuestLogger(debug=debug, agent=agent_id)

        # Set quest file for logging
        logger.set_quest_file(quest_path)

        # Create quest environment
        env = QuestEnvironment(quest_path)

        # Create quest runner with callbacks
        runner = QuestRunner(agent=agent, debug=debug, callbacks=callbacks or [])

        # Run quest with timeout
        with ThreadPoolExecutor() as executor:
            future = executor.submit(runner.run, quest_path)
            try:
                outcome = future.result(timeout=timeout)

                # Update run with agent_id and config if provided
                if agent_id or agent_config:
                    logger.cursor.execute('''
                        UPDATE runs
                        SET agent_id = ?, agent_config = ?
                        WHERE id = ?
                    ''', (agent_id, agent_config, logger.current_run_id))
                    logger.conn.commit()

                return outcome
            except TimeoutError:
                logger.logger.warning(f"Quest timed out after {timeout} seconds")
                return None

    except Exception as e:
        logger.logger.error(f"Error running quest: {e}")
        raise

class QuestRunner:
    """Manages quest execution with logging and metrics"""
    def __init__(self, agent: QuestPlayer, debug: bool = False, logger: Any = None,
                 callbacks: List[Callable[[str, Any], None]] = None):
        """Initialize all components needed for quest execution"""
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
            self.env = QuestEnvironment(quest, language=DEFAULT_LANG, debug=self.debug)
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
            # Initialize environment and logger
            self.initialize(quest)
            if self.debug:
                self.logger.debug("Environment initialized successfully")

            self._notify_callbacks("title")
            self._notify_callbacks("progress", {"step": 0, "message": "Starting quest..."})

            # Get initial state
            observation = self.env.reset()
            if self.debug:
                self.logger.debug("Initial state: %s", self.env.state)

            while True:
                self.step_count += 1
                if self.debug:
                    self.logger.debug("Step %d: Processing action", self.step_count)

                self._notify_callbacks("progress", {
                    "step": self.step_count,
                    "message": f"Processing step {self.step_count}..."
                })

                # Check if there are any choices available
                if not self.env.state['choices']:
                    if self.debug:
                        self.logger.debug("No more choices available - quest ended")
                    if self.env and self.env.state:
                        self.agent.on_game_end(self.env.state)
                    return QuestOutcome.FAILURE

                # Get agent's action
                action = self.agent.get_action(observation, self.env.state['choices'])
                if self.debug:
                    self.logger.debug("Agent selected action: %s", action)

                try:
                    # Take action in environment
                    step_result = self.env.step(action)
                    observation, done, success, info = step_result

                    # Create agent state for rendering
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
                        # Quest completed
                        if success:
                            self._notify_callbacks("progress", {
                                "step": self.step_count,
                                "message": "Quest completed successfully!"
                            })
                            if self.debug:
                                self.logger.debug("Quest completed successfully!")
                            self.agent.on_game_end(self.env.state)
                            return QuestOutcome.SUCCESS
                        else:
                            self._notify_callbacks("progress", {
                                "step": self.step_count,
                                "message": "Quest failed."
                            })
                            if self.debug:
                                self.logger.debug("Quest failed.")
                            self.agent.on_game_end(self.env.state)
                            return QuestOutcome.FAILURE

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