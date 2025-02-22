"""Quest runner implementation with improved logging and error handling"""
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from llm_quest_benchmark.agents.base import QuestPlayer
from llm_quest_benchmark.agents.llm_agent import LLMAgent
from llm_quest_benchmark.environments.qm import QMPlayerEnv
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.core.logging import QuestLogger, LogManager
from llm_quest_benchmark.core.time import run_with_timeout, CommandTimeout
from llm_quest_benchmark.constants import DEFAULT_LANG, DEFAULT_QUEST_TIMEOUT
from llm_quest_benchmark.renderers.terminal import RichRenderer
from llm_quest_benchmark.renderers.null import NoRenderer
from llm_quest_benchmark.renderers.base import BaseRenderer
from llm_quest_benchmark.dataclasses.state import AgentState, QMState

# Configure logging
logging.getLogger('quest').setLevel(logging.WARNING)
logging.getLogger('LLMAgent').setLevel(logging.WARNING)

def run_quest_with_timeout(
    quest_path: str,
    agent: QuestPlayer,
    timeout: int = DEFAULT_QUEST_TIMEOUT,
    debug: bool = True,
    renderer: Optional[BaseRenderer] = None,
) -> Dict[str, Any]:
    """Run a single quest with timeout and parameters

    Args:
        quest_path (str): Path to quest file
        agent (QuestPlayer): Agent to run quest with
        timeout (int, optional): Timeout in seconds. Defaults to DEFAULT_QUEST_TIMEOUT.
        debug (bool, optional): Enable debug output. Defaults to True.
        renderer (Optional[BaseRenderer], optional): Renderer to use. Defaults to None.

    Returns:
        Dict[str, Any]: Quest run result with outcome and metrics
    """
    quest_name = Path(quest_path).name
    result = {
        'quest': quest_name,
        'timestamp': datetime.now().isoformat(),
        'outcome': QuestOutcome.ERROR.name,
        'error': None,
        'steps': [],
        'llm_error': False
    }

    logger = logging.getLogger(__name__)
    if debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    try:
        logger.info(f"Starting quest {quest_name} with agent {agent}")

        runner = QuestRunner(agent=agent, debug=debug, renderer=renderer)
        try:
            # Run quest with timeout
            def run_quest():
                return runner.run(quest_path)
            outcome = run_with_timeout(run_quest, timeout)
            result['outcome'] = outcome.name
        except CommandTimeout:
            logger.warning(f"Quest {quest_name} timed out after {timeout} seconds")
            result['outcome'] = QuestOutcome.TIMEOUT.name
            result['error'] = f"Timed out after {timeout} seconds"

        # Collect detailed metrics from quest logger
        if runner.quest_logger:
            result['steps'] = runner.quest_logger.get_log_entries()

        # Check for LLM errors
        if isinstance(agent, LLMAgent):
            result['llm_error'] = getattr(agent, 'last_error', None) is not None
            if result['llm_error']:
                result['error'] = f"LLM Error: {agent.last_error}"

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        logger.error(f"Quest {quest_name} failed with error: {error_msg}")
        result['error'] = error_msg
        if isinstance(agent, LLMAgent):
            result['llm_error'] = getattr(agent, 'last_error', None) is not None

    return result


class QuestRunner:
    """Manages quest execution with logging and metrics"""
    def __init__(self, agent: QuestPlayer, debug: bool = False, logger: Any = None, renderer: Optional[BaseRenderer] = None):
        """Initialize all components needed for quest execution"""
        self.agent = agent
        self.debug = debug

        self.logger = logger
        if logger is None:
            log_manager = LogManager()
            log_manager.setup(debug=debug)
            self.logger = log_manager.get_logger()

        # Use provided renderer or create default one
        self.renderer = renderer or (NoRenderer() if debug else RichRenderer())

        self.step_count = 0
        self.env = None

        # Initialize quest logger
        self.quest_logger = QuestLogger(
            debug=self.debug,
            agent=str(self.agent)
        )

        if debug:
            self.logger.debug("QuestRunner initialized with agent: %s", str(agent))

    def initialize(self, quest: str) -> None:
        """Initialize environment and logger for a new quest"""
        try:
            if self.debug:
                self.logger.debug("Initializing environment for quest: %s", quest)
            self.env = QMPlayerEnv(quest, language=DEFAULT_LANG, debug=self.debug)
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

            self.renderer.render_title()

            # Get initial state
            observation = self.env.reset()
            if self.debug:
                self.logger.debug("Initial state: %s", self.env.state)

            # Start with step 0
            self.step_count = 0

            while True:
                self.step_count += 1
                if self.debug:
                    self.logger.debug("Step %d: Processing action", self.step_count)

                # Check if there are any choices available
                if not self.env.state['choices']:
                    if self.debug:
                        self.logger.debug("No more choices available - quest ended")
                    if self.env and self.env.state:
                        self.agent.on_game_end(self.env.state)
                    return QuestOutcome.FAILURE

                # Create agent state for current observation and choices
                agent_state = AgentState(
                    step=self.step_count,
                    location_id=self.env.state['location_id'],
                    observation=observation,
                    choices=self.env.state['choices'],
                    action="",  # Will be set after getting action
                    llm_response=None  # Will be set after getting action
                )

                # Get agent's action
                action = self.agent.get_action(observation, self.env.state['choices'])
                if self.debug:
                    self.logger.debug("Agent selected action: %s", action)

                # Update state with agent's action and response
                agent_state.action = str(action)
                agent_state.llm_response = self.agent.get_last_response()

                # Render and log the state
                self.renderer.render_game_state(agent_state)
                if self.quest_logger:
                    self.quest_logger.log_step(agent_state)

                try:
                    # Take action in environment
                    step_result = self.env.step(action)
                    observation, done, success, info = step_result

                    if done:
                        # Quest completed
                        if success:
                            if self.debug:
                                self.logger.debug("Quest completed successfully!")
                            self.agent.on_game_end(self.env.state)
                            return QuestOutcome.SUCCESS
                        else:
                            if self.debug:
                                self.logger.debug("Quest failed.")
                            self.agent.on_game_end(self.env.state)
                            return QuestOutcome.FAILURE

                except Exception as e:
                    self.logger.error("Error during step: %s", str(e), exc_info=True)
                    raise

        except Exception as e:
            self.logger.error("Error running quest: %s", str(e), exc_info=True)
            if self.env and self.env.state:
                self.agent.on_game_end(self.env.state)
            return QuestOutcome.ERROR