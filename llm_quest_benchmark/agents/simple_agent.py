"""Simple LLM agent for Space Rangers quests without TextArena dependencies"""
import logging
from typing import Dict, List, Any

from jinja2 import Environment as JinjaEnvironment
from jinja2 import FileSystemLoader

from llm_quest_benchmark.constants import PROMPT_TEMPLATES_DIR, MODEL_CHOICES
from llm_quest_benchmark.agents.llm_client import get_llm_client
from llm_quest_benchmark.agents.base import QuestPlayer

# Configure Jinja environment
env = JinjaEnvironment(loader=FileSystemLoader(PROMPT_TEMPLATES_DIR),
                      trim_blocks=True,
                      lstrip_blocks=True)


class SimpleQuestAgent(QuestPlayer):
    """Basic LLM agent for Space Rangers quests"""

    SUPPORTED_MODELS = MODEL_CHOICES

    def __init__(self, debug: bool = False, model_name: str = "gpt-4o"):
        self.debug = debug
        self.model_name = model_name.lower()
        if self.model_name not in self.SUPPORTED_MODELS:
            raise ValueError(f"Unsupported model: {model_name}. Supported models are: {self.SUPPORTED_MODELS}")

        self.logger = logging.getLogger(self.__class__.__name__)
        if self.debug:
            self.logger.setLevel(logging.DEBUG)
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(name)s - %(message)s'))
            self.logger.addHandler(handler)

        # Load templates
        self.action_template = env.get_template("action_choice.jinja")
        self.system_template = env.get_template("system_role.jinja")

        # Initialize LLM client
        self.llm = get_llm_client(model_name)
        self.history = []

    def get_action(self, observation: str, choices: list) -> str:
        """Process observation and return action number"""
        if self.debug:
            self.logger.debug(f"\nObservation:\n{observation}")

        # Format choices for template
        choice_list = [{"text": c["text"]} for c in choices]

        # Render prompt using template
        prompt = self.action_template.render(observation=observation, choices=choice_list)
        if self.debug:
            self.logger.debug(f"\nPrompt:\n{prompt}")

        try:
            response = self.llm(prompt)
            if self.debug:
                self.logger.debug(f"Raw LLM response: {response}")

            # Ensure response is a valid choice number
            choice_num = response.strip()
            if not choice_num.isdigit() or not (1 <= int(choice_num) <= len(choices)):
                self.logger.error(f"Invalid choice number: {choice_num}")
                return "1"  # Default to first choice

            return choice_num

        except Exception as e:
            self.logger.error(f"LLM call failed: {str(e)}")
            return "1"  # Default to first choice

    def reset(self) -> None:
        """Reset agent state"""
        self.history = []

    def on_game_end(self, final_state: Dict[str, Any]) -> None:
        """Log final state for analysis"""
        if self.debug:
            self.logger.debug(f"Game ended with state: {final_state}")