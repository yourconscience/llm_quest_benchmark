"""Quest runner implementation with improved logging and error handling"""
import logging
from typing import Optional, Dict, Any

from llm_quest_benchmark.constants import DEFAULT_MODEL, DEFAULT_LANG
from llm_quest_benchmark.agents.simple_agent import SimpleQuestAgent
from llm_quest_benchmark.environments.qm import QMPlayerEnv
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
        self.env = QMPlayerEnv(quest, language=language, debug=debug)

        self.logger.debug("Initializing agent...")
        self.agent = SimpleQuestAgent(debug=debug, model_name=model)
        self.logger.info(f"Using model: {model}")
        self.logger.info(f"Using language: {language}")

        self.logger.debug("Initializing renderer...")
        self.renderer = QuestRenderer(self.env)

        if metrics:
            self.logger.debug("Setting up metrics logging...")
            self.metrics_logger = MetricsLogger(auto_save=True)
            self.metrics_logger.set_quest_file(quest)

    def run(self) -> int:
        """Run the quest until completion or error

        Returns:
            int: Exit code (0 for success, 1 for failure)
        """
        if not self.env or not self.agent:
            self.logger.error("Runner not initialized!")
            return 1

        try:
            # Get initial state
            observation = self.env.reset()
            self.renderer.render()

            while True:
                # Get agent's action
                action = self.agent.get_action(observation, self.env.state['choices'])

                # Take action in environment
                observation, reward, done, info = self.env.step(action)

                # Render current state
                self.renderer.render()

                # Log metrics if enabled
                if self.metrics_logger:
                    self.metrics_logger.log_step(
                        step=len(self.env.state_history),
                        state=self.env.state,
                        action=action,
                        reward=reward
                    )

                if done:
                    # Quest completed
                    final_reward = reward if isinstance(reward, (int, float)) else reward.get(0, 0)  # Get player reward
                    if final_reward > 0:
                        self.logger.info("Quest completed successfully!")
                        return 0
                    else:
                        self.logger.info("Quest failed.")
                        return 1

        except Exception as e:
            self.logger.exception("Error during quest execution")
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