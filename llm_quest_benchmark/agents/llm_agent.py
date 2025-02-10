"""
LLM-powered agent for Space Rangers quests using TextArena's agent system
"""
import logging

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

    def __init__(self, debug: bool = False, model_name: str = "openai"):
        super().__init__(player_id=0) # Agent for player 0
        self.debug = debug
        self.model_name = model_name.lower() # Store model name
        if self.model_name not in self.SUPPORTED_MODELS: # Validate model name
            raise ValueError(f"Unsupported model: {model_name}. Supported models are: {self.SUPPORTED_MODELS}")
        self.logger = logging.getLogger(self.__class__.__name__)
        self.action_template = env.get_template("action_choice.jinja")
        self.system_template = env.get_template("system_role.jinja")

        # Initialize agent based on model_name
        if self.model_name == "gpt-4o":
            self.agent = ta.agents.OpenRouterAgent(model_kwargs={"max_tokens": 200}, model_ids=["openai/gpt-4o"]) # Example OpenAI model
        elif self.model_name == "sonnet":
            self.agent = ta.agents.OpenRouterAgent(model_kwargs={"max_tokens": 200}, model_ids=["anthropic/claude-3.5-sonnet"]) # Example Anthropic model
        elif self.model_name == "deepseek":
            self.agent = ta.agents.OpenRouterAgent(model_kwargs={"max_tokens": 200}, model_ids=["deepseek-ai/deepseek-chat"]) # Example DeepSeek model
        else:
            # Should not reach here due to validation in __init__
            raise ValueError(f"Model name '{model_name}' is not supported.")

        self.reset()

        if self.debug:
            self.logger.setLevel(logging.DEBUG)
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(name)s - %(message)s'))
            self.logger.addHandler(handler)

    def reset(self):
        pass

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
            response = self.agent(prompt)
            if self.debug:
                self.logger.debug(f"Raw LLM response: {response}")
            return response
        except Exception as e:
            self.logger.error(f"LLM call failed: {str(e)}")
            return "0"


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
