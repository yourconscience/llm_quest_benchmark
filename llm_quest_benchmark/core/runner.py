"""Quest runner implementation with improved logging and error handling"""
import logging
from typing import Optional, Dict, Any
import json

from llm_quest_benchmark.constants import DEFAULT_MODEL, DEFAULT_LANG, DEFAULT_TEMPLATE
from llm_quest_benchmark.agents.llm_agent import LLMAgent
from llm_quest_benchmark.environments.qm import QMPlayerEnv
from llm_quest_benchmark.renderers.terminal import TerminalRenderer
from llm_quest_benchmark.renderers.prompt_renderer import PromptRenderer
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.core.logging import QuestLogger


class QuestRunner:
    """Manages quest execution with logging and metrics"""
    def __init__(self, logger: Optional[logging.Logger] = None, headless: bool = False):
        self.logger = logger or logging.getLogger(__name__)
        self.env = None
        self.agent = None
        self.terminal = None if headless else TerminalRenderer()
        self.prompt_renderer = None  # Initialize in initialize()
        self.quest_logger = None
        self.step_count = 0

    def initialize(
        self,
        quest: str,
        model: str = DEFAULT_MODEL,
        language: str = DEFAULT_LANG,
        debug: bool = False,
        headless: bool = False,
        template: str = DEFAULT_TEMPLATE,
    ) -> None:
        """Initialize all components needed for quest execution"""
        self.logger.debug("Initializing environment...")
        self.env = QMPlayerEnv(quest, language=language, debug=debug)

        self.logger.debug("Initializing agent...")
        self.agent = LLMAgent(debug=debug, model_name=model, template=template)
        self.logger.info(f"Using model: {model}")
        self.logger.info(f"Using language: {language}")

        # Initialize prompt renderer
        self.prompt_renderer = PromptRenderer(self.env, template=template)

        # Initialize unified logger
        self.quest_logger = QuestLogger(
            debug=debug,
            is_llm=True,
            model=model,
            template=template
        )
        self.quest_logger.set_quest_file(quest)

        # Initialize terminal renderer if not headless
        self.terminal = None if headless else TerminalRenderer()

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
            if self.terminal:
                self.terminal.render_game_state(self.env.state)

            while True:
                self.step_count += 1

                # Get agent's action
                prompt = self.prompt_renderer.render_action_prompt(observation, self.env.state['choices'])
                action = self.agent.get_action(observation, self.env.state['choices'])

                # Take action in environment
                observation, reward, done, info = self.env.step(action)

                # Add to history and log
                self.prompt_renderer.add_to_history(self.env.state)
                if self.quest_logger:
                    self.quest_logger.log_step(
                        step=self.step_count,
                        state=observation,
                        choices=self.env.state['choices'],
                        prompt=prompt,
                        response=action,
                        reward=reward,
                        metrics=info
                    )

                # Optional terminal rendering
                if self.terminal:
                    self.terminal.render_game_state(self.env.state)

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

    def _format_prompt(self, observation: str, choices: list) -> str:
        """Format the prompt that will be sent to the agent"""
        return f"""Observation:
{observation}

Available actions:
{json.dumps(choices, indent=2)}

Choose your action (respond with just the number):"""


def run_quest(
    quest: str,
    model: str = DEFAULT_MODEL,
    language: str = DEFAULT_LANG,
    debug: bool = False,
    headless: bool = False,
    template: str = DEFAULT_TEMPLATE,
) -> QuestOutcome:
    """Convenience function to run a quest with minimal setup
    Returns:
        QuestOutcome: The final outcome of the quest
    """
    runner = QuestRunner(headless=headless)
    runner.initialize(
        quest=quest,
        model=model,
        language=language,
        debug=debug,
        headless=headless,
        template=template,
    )
    return runner.run()