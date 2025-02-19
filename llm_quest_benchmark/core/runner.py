"""Quest runner implementation with improved logging and error handling"""
import logging
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

from llm_quest_benchmark.agents.base import QuestPlayer
from llm_quest_benchmark.environments.qm import QMPlayerEnv
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.core.logging import QuestLogger, LogManager
from llm_quest_benchmark.core.time import run_with_timeout, CommandTimeout
from llm_quest_benchmark.constants import DEFAULT_LANG, DEFAULT_QUEST_TIMEOUT
from llm_quest_benchmark.renderers.terminal import RichRenderer, NoRenderer

def run_quest_with_timeout(
    quest_path: str,
    agent: QuestPlayer,
    timeout: int = DEFAULT_QUEST_TIMEOUT,
    debug: bool = True,
) -> Dict[str, Any]:
    """Run a single quest with timeout and parameters

    Args:
        quest_path (str): Path to quest file
        agent (QuestPlayer): Agent to use for quest execution
        timeout (int, optional): Timeout in seconds. Defaults to 60.
        debug (bool, optional): Enable debug mode. Defaults to False.
        skip_single (bool, optional): Auto-select single choices. Defaults to False.

    Returns:
        Dict[str, Any]: Result dictionary with quest outcome and metrics
    """
    quest_name = Path(quest_path).name
    result = {
        'quest': quest_name,
        'agent': str(agent),
        'outcome': QuestOutcome.ERROR.name,  # Store as string
        'error': None,
        'timestamp': datetime.now().isoformat(),
        'steps': []  # Store detailed steps
    }

    logger = logging.getLogger(__name__)
    if debug:
        logger.setLevel(logging.DEBUG)

    try:
        logger.info(f"Starting quest {quest_name} with agent {agent}")

        runner = QuestRunner(agent=agent, debug=debug)
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

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        logger.error(f"Quest {quest_name} failed with error: {error_msg}")
        result['error'] = error_msg

    return result


class QuestRunner:
    """Manages quest execution with logging and metrics"""
    def __init__(self, agent: QuestPlayer, debug: bool = False, logger: Any = None):
        """Initialize all components needed for quest execution"""
        self.agent = agent
        self.debug = debug

        self.logger = logger
        if logger is None:
            log_manager = LogManager()
            log_manager.setup(debug=debug)
            self.logger = log_manager.get_logger()

        self.renderer = RichRenderer() if not debug else NoRenderer()

        self.step_count = 0
        self.env = None

        # Initialize quest logger
        self.quest_logger = QuestLogger(
            debug=self.debug,
            agent=str(self.agent)
        )

        self.logger.debug("QuestRunner initialized with agent: %s", str(agent))

    def initialize(self, quest: str) -> None:
        """Initialize environment and logger for a new quest"""
        try:
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
            self.logger.debug("Environment initialized successfully")

            self.renderer.render_title()

            # Get initial state
            observation = self.env.reset()
            self.logger.debug("Initial observation: %s", observation)
            self.logger.debug("Initial state: %s", self.env.state)

            self.renderer.render_game_state(self.env.state)

            while True:
                self.step_count += 1
                self.logger.debug("Step %d: Processing action", self.step_count)

                # Check if there are any choices available
                if not self.env.state['choices']:
                    self.logger.info("No more choices available - quest ended")
                    if self.env and self.env.state:
                        self.agent.on_game_end(self.env.state)
                    return QuestOutcome.FAILURE

                # Get agent's action
                action = self.agent.get_action(observation, self.env.state['choices'])
                self.logger.debug("Agent selected action: %s (type: %s)", action, type(action))

                try:
                    # Take action in environment
                    step_result = self.env.step(action)
                    self.logger.debug("Raw step result: %s", step_result)

                    observation, done, success, info = step_result
                    self.logger.debug("Step result unpacked - observation: %s, done: %s, success: %s, info: %s",
                                 observation[:100] + "..." if observation and len(observation) > 100 else observation,
                                 done, success, info)

                    self.renderer.render_game_state(self.env.state)

                    if self.quest_logger:
                        self.quest_logger.log_step(
                            step=self.step_count,
                            state=observation,
                            choices=self.env.state['choices'],
                            response=action,
                            reward=info.get('reward', 0),
                            metrics=info,
                            llm_response=None
                        )

                    if done:
                        # Quest completed
                        if success:
                            self.logger.warning("Quest completed successfully!")
                            self.agent.on_game_end(self.env.state)
                            return QuestOutcome.SUCCESS
                        else:
                            self.logger.warning("Quest failed.")
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