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
from llm_quest_benchmark.constants import DEFAULT_LANG

def run_quest_with_timeout(
    quest_path: str,
    agent: QuestPlayer,
    timeout_seconds: int = 60,
    debug: bool = True,
    skip_single: bool = False,
) -> Dict[str, Any]:
    """Run a single quest with timeout and parameters

    Args:
        quest_path (str): Path to quest file
        agent (QuestPlayer): Agent to use for quest execution
        timeout_seconds (int, optional): Timeout in seconds. Defaults to 60.
        debug (bool, optional): Enable debug mode. Defaults to False.
        skip_single (bool, optional): Auto-select single choices. Defaults to False.
        headless (bool, optional): Run without terminal UI. Defaults to True.

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

        runner = QuestRunner(agent=agent, debug=debug, skip_single=skip_single)
        try:
            # Run quest with timeout
            outcome = run_with_timeout(runner.run, timeout_seconds)
            result['outcome'] = outcome.name
        except CommandTimeout:
            logger.warning(f"Quest {quest_name} timed out after {timeout_seconds} seconds")
            result['outcome'] = QuestOutcome.TIMEOUT.name
            result['error'] = f"Timed out after {timeout_seconds} seconds"

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
    def __init__(self, agent: QuestPlayer, debug: bool = True, skip_single: bool = False):
        """Initialize all components needed for quest execution"""
        self.agent = agent
        self.debug = debug
        self.skip_single = skip_single
        self.logger = LogManager().get_logger(debug=debug)
        self.step_count = 0

        # Initialize unified logger
        self.quest_logger = QuestLogger(
            debug=debug,
            agent=str(self.agent)
        )


    def run(self, quest: str) -> QuestOutcome:
        """Run the quest until completion or error

        Returns:
            QuestOutcome: The final outcome of the quest
        """
        if not self.agent:
            self.logger.error("No agent initialized!")
            return QuestOutcome.ERROR

        self.logger.debug("Initializing environment...")
        self.env = QMPlayerEnv(quest, language=DEFAULT_LANG, debug=self.debug)
        self.quest_logger.set_quest_file(quest)
        self.logger.info(f"Running quest {quest} with agent: {str(self.agent)}")
        try:
            # Get initial state
            observation = self.env.reset()

            while True:
                self.step_count += 1

                # Get agent's action
                action = self.agent.get_action(observation, self.env.state['choices'])

                # Get full LLM response if available
                llm_response = None
                try:
                    llm_response = self.agent.get_last_response()
                except AttributeError:
                    llm_response = None

                # Take action in environment
                observation, reward, done, info = self.env.step(action)

                if self.quest_logger:
                    self.quest_logger.log_step(
                        step=self.step_count,
                        state=observation,
                        choices=self.env.state['choices'],
                        response=action,
                        reward=reward,
                        metrics=info,
                        llm_response=llm_response
                    )

                if done:
                    # Quest completed
                    final_reward = reward if isinstance(reward, (int, float)) else reward.get(0, 0)
                    if final_reward > 0:
                        self.logger.info("Quest completed successfully!")
                        return QuestOutcome.SUCCESS
                    else:
                        self.logger.info("Quest failed.")
                        return QuestOutcome.FAILURE

        except Exception as e:
            self.logger.exception("Error during quest execution")
            return QuestOutcome.ERROR