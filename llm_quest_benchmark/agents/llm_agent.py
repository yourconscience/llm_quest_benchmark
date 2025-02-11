"""
LLM-powered agent for Space Rangers quests using TextArena's agent system
"""
import logging
import re
import os
import sys
from openai import OpenAI

import textarena as ta
from jinja2 import Environment as JinjaEnvironment
from jinja2 import FileSystemLoader

from llm_quest_benchmark.constants import PROMPT_TEMPLATES_DIR
from llm_quest_benchmark.constants import MODEL_CHOICES

# Configure Jinja environment
env = JinjaEnvironment(loader=FileSystemLoader(PROMPT_TEMPLATES_DIR),
                       trim_blocks=True,
                       lstrip_blocks=True)


class QuestAgent(ta.Agent):
    """TextArena agent specialized for Space Rangers quests"""

    SUPPORTED_MODELS = MODEL_CHOICES
    MODEL_NAME = "gpt-4o-mini"  # Using gpt-4o-mini directly

    def __init__(self, debug: bool = False, model_name: str = "gpt-4o"):
        super().__init__()  # Initialize base Agent class
        self.player_id = 0  # Set player_id after initialization
        self.debug = debug

        # Configure logging
        self.logger = logging.getLogger(self.__class__.__name__)
        if self.debug:
            self.logger.setLevel(logging.DEBUG)
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))
            self.logger.addHandler(handler)

        # Load templates
        self.action_template = env.get_template("action_choice.jinja")
        self.system_template = env.get_template("system_role.jinja")

        # Get system prompt
        system_prompt = self.system_template.render()
        if self.debug:
            self.logger.debug(f"System prompt:\n{system_prompt}")

        # Initialize OpenAI client
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")
            self.client = OpenAI(api_key=api_key)
            if self.debug:
                self.logger.debug(f"Initialized OpenAI client with model: {self.MODEL_NAME}")
        except Exception as e:
            self.logger.error(f"Failed to initialize OpenAI client: {str(e)}")
            sys.exit(1)  # Exit immediately on initialization error

        self.reset()

    def reset(self):
        """Reset agent state"""
        self.history = []
        self.logger.debug("Agent state reset")

    def extract_choice_number(self, response: str) -> str:
        """Extract choice number from LLM response"""
        # Try to find a number in the response
        match = re.search(r'\d+', response.strip())
        if match:
            return match.group(0)
        self.logger.error("No valid choice number found in response")
        sys.exit(1)  # Exit immediately if no valid choice found

    def __call__(self, observation: str) -> str:
        """Process observation and return action number"""
        if self.debug:
            self.logger.debug(f"\nObservation:\n{observation}")

        # Parse choices from observation text
        lines = observation.split('\n')
        choices = []
        collecting = False

        for line in lines:
            if line.startswith('Available actions:') or line.startswith('Available choices:'):
                collecting = True
                continue
            if collecting and line.strip():
                # Extract choice text without number
                text = line.split('.', 1)[1].strip() if '.' in line else line.strip()
                choices.append({"text": text})

        if not choices:
            self.logger.error("No valid choices found in observation!")
            sys.exit(1)  # Exit immediately if no choices found

        # Render prompt using template
        prompt = self.action_template.render(observation=observation, choices=choices)
        if self.debug:
            self.logger.debug(f"\nPrompt:\n{prompt}")

        try:
            response = self.client.chat.completions.create(
                model=self.MODEL_NAME,
                messages=[
                    {"role": "system", "content": self.system_template.render()},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.7
            )
            if self.debug:
                self.logger.debug(f"Raw LLM response: {response.choices[0].message.content}")

            # Extract choice number from response
            choice = self.extract_choice_number(response.choices[0].message.content)
            if self.debug:
                self.logger.debug(f"Extracted choice: {choice}")

            # Store in history
            self.history.append({
                'observation': observation,
                'prompt': prompt,
                'response': response.choices[0].message.content,
                'choice': choice
            })

            return choice

        except Exception as e:
            self.logger.error(f"OpenAI API call failed: {str(e)}")
            sys.exit(1)  # Exit immediately on any error


# Optional wrapper for more strategic gameplay
class StrategicQuestAgent(ta.AgentWrapper):
    """Adds strategic thinking to quest agent responses"""

    def __init__(self, agent: QuestAgent, debug: bool = False):
        super().__init__(agent)
        self.debug = debug

    def __call__(self, observation: str) -> str:
        # First, analyze the situation
        analysis = self.agent(
            "Analyze this situation and explain your thinking step-by-step instead of choosing an action:\n"
            + observation)
        if self.debug:
            print(f"\nAnalysis: {analysis}")

        # Then make the actual choice
        action = self.agent(f"{observation}\n\nAnalysis:\n{analysis}")
        if self.debug:
            print(f"Chosen action: {action}")

        return action
