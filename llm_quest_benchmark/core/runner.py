"""Quest runner implementation with improved logging and error handling"""
import logging
from typing import Optional, Tuple, Dict, Any

from llm_quest_benchmark.constants import DEFAULT_MODEL, DEFAULT_LANG
from llm_quest_benchmark.agents.llm_agent import QuestAgent
from llm_quest_benchmark.environments.qm_env import QMPlayerEnv
from llm_quest_benchmark.renderers.quest_renderer import QuestRenderer
from llm_quest_benchmark.metrics import MetricsLogger


class QuestRunner:
    """Manages quest execution with logging and metrics"""
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.env = None
        self.agent = None
        self.renderer = None
        self.metrics_logger = None

    def initialize(
        self,
        quest: str,
        model: str = DEFAULT_MODEL,
        language: str = DEFAULT_LANG,
        debug: bool = False,
        metrics: bool = False
    ) -> None:
        """Initialize all components needed for quest execution"""
        self.logger.debug("Initializing environment...")
        self.env = QMPlayerEnv(quest, language=language)

        self.logger.debug("Initializing agent...")
        self.agent = QuestAgent(debug=debug, model_name=model)
        self.logger.info(f"Using model: {model}")
        self.logger.info(f"Using language: {language}")

        self.renderer = QuestRenderer(self.env)

        if metrics:
            self.logger.debug("Setting up metrics logging...")
            self.metrics_logger = MetricsLogger(auto_save=True)
            self.metrics_logger.set_quest_file(quest)

    def execute_step(self) -> Tuple[bool, float, Dict[str, Any]]:
        """Execute a single step of the quest
        Returns:
            Tuple[bool, float, dict]: (is_done, reward, info)
        """
        self.logger.debug(f"Getting action from agent...")
        action = self.agent(self.env.state.observations[0])
        self.logger.debug(f"Agent chose action: {action}")

        observations, rewards, done, info = self.env.step(action)
        reward = rewards[0]

        if self.metrics_logger:
            self.metrics_logger.log_step(
                self.env.metrics['steps_taken'],
                observations,
                action,
                reward
            )

        self.logger.debug(f"Step complete. Reward: {reward}")
        return done, reward, info

    def run(self) -> int:
        """Run the quest to completion
        Returns:
            int: Exit code (0 for success, 1 for failure)
        """
        try:
            self.logger.debug("Resetting environment...")
            self.env.reset()
            total_reward = 0

            while True:
                done, reward, info = self.execute_step()
                total_reward += reward

                if done:
                    if reward > 0:
                        self.logger.info("🎉 Quest completed successfully!")
                    else:
                        self.logger.info("💥 Quest failed!")
                    break

            if self.metrics_logger:
                self.logger.debug("Saving metrics...")
                self.metrics_logger.save()

            return 0 if total_reward > 0 else 1

        except Exception as e:
            self.logger.exception("Error during quest run")
            return 1


def run_quest(
    quest: str,
    log_level: str = "info",
    model: str = DEFAULT_MODEL,
    language: str = DEFAULT_LANG,
    metrics: bool = False,
    logger: Optional[logging.Logger] = None,
) -> int:
    """Convenience function to run a quest with minimal setup
    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    runner = QuestRunner(logger=logger)
    runner.initialize(
        quest=quest,
        model=model,
        language=language,
        debug=(log_level.upper() == "DEBUG"),
        metrics=metrics
    )
    return runner.run()