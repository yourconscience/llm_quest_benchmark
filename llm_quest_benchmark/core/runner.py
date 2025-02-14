"""Quest runner implementation with improved logging and error handling"""
import logging
from typing import Optional, Dict, Any

from llm_quest_benchmark.constants import DEFAULT_MODEL, DEFAULT_LANG
from llm_quest_benchmark.agents.llm_agent import LLMAgent
from llm_quest_benchmark.environments.qm import QMPlayerEnv
from llm_quest_benchmark.renderers.quest_renderer import QuestRenderer
from llm_quest_benchmark.metrics import MetricsLogger
from llm_quest_benchmark.environments.state import QuestOutcome


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
        self.agent = LLMAgent(debug=debug, model_name=model)
        self.logger.info(f"Using model: {model}")
        self.logger.info(f"Using language: {language}")

        self.logger.debug("Initializing renderer...")
        self.renderer = QuestRenderer(self.env)

        if metrics:
            self.logger.debug("Setting up metrics logging...")
            self.metrics_logger = MetricsLogger(auto_save=True)
            self.metrics_logger.set_quest_file(quest)

    def run(self) -> QuestOutcome:
        """Run the quest until completion or error

        Returns:
            QuestOutcome: The final outcome of the quest
        """
        if not self.env or not self.agent:
            self.logger.error("Runner not initialized!")
            return QuestOutcome.ERROR

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
                        return QuestOutcome.SUCCESS
                    else:
                        self.logger.info("Quest failed.")
                        return QuestOutcome.FAILURE

        except Exception as e:
            self.logger.exception("Error during quest execution")
            return QuestOutcome.ERROR


def run_quest(
    quest: str,
    log_level: str = "info",
    model: str = DEFAULT_MODEL,
    language: str = DEFAULT_LANG,
    metrics: bool = False,
    logger: Optional[logging.Logger] = None,
) -> QuestOutcome:
    """Convenience function to run a quest with minimal setup
    Returns:
        QuestOutcome: The final outcome of the quest
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