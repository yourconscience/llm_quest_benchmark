"""Simple LLM agent for Space Rangers quests without TextArena dependencies"""
import logging
from typing import Dict, List, Optional

from jinja2 import Environment as JinjaEnvironment
from jinja2 import FileSystemLoader

from llm_quest_benchmark.constants import PROMPT_TEMPLATES_DIR, MODEL_CHOICES
from llm_quest_benchmark.agents.llm_client import get_llm_client

# Configure Jinja environment
env = JinjaEnvironment(loader=FileSystemLoader(PROMPT_TEMPLATES_DIR),
                      trim_blocks=True,
                      lstrip_blocks=True)


class SimpleQuestAgent:
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

    def __call__(self, observation: str) -> str:
        """Process observation and return action number"""
        if self.debug:
            self.logger.debug(f"\nObservation:\n{observation}")

        # Parse choices from observation text
        lines = observation.split('\n')
        choices = []
        collecting = False

        for line in lines:
            if line.startswith('Available actions:'):
                collecting = True
                continue
            if collecting and line.strip():
                # Extract choice text without number
                text = line.split('.', 1)[1].strip()
                choices.append({"text": text})

        if not choices:
            self.logger.error("No valid choices found in observation!")
            return "0"  # Emergency exit

        # Render prompt using template
        prompt = self.action_template.render(observation=observation, choices=choices)
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
                return "0"

            return choice_num

        except Exception as e:
            self.logger.error(f"LLM call failed: {str(e)}")
            return "0"  # Emergency exit


class StrategicSimpleAgent:
    """Adds strategic thinking to simple quest agent responses"""

    def __init__(self, agent: SimpleQuestAgent, debug: bool = False):
        self.agent = agent
        self.debug = debug

    def __call__(self, observation: str) -> str:
        # First, analyze the situation
        analysis = self.agent.llm(
            "Analyze this situation and explain your thinking step-by-step instead of choosing an action:\n"
            + observation)
        if self.debug:
            print(f"\nAnalysis: {analysis}")

        # Then make the actual choice
        action = self.agent(f"{observation}\n\nAnalysis:\n{analysis}")
        if self.debug:
            print(f"Chosen action: {action}")

        return action