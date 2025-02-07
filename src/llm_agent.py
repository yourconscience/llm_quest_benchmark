"""
LLM-powered agent for Space Rangers quests using TextArena's agent system
"""
import textarena as ta
from typing import Optional
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# Configure Jinja environment
TEMPLATES_DIR = Path(__file__).parent / "prompt_templates"
env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    trim_blocks=True,
    lstrip_blocks=True
)

class QuestAgent(ta.Agent):
    """TextArena agent specialized for Space Rangers quests"""

    def __init__(
        self,
        model: str = "claude-3.5-sonnet",
        temperature: float = 0.4,
        **kwargs
    ):
        super().__init__()
        # Load templates
        self.system_template = env.get_template("system_role.jinja")
        self.action_template = env.get_template("action_choice.jinja")

        # Initialize agent with rendered system prompt
        self.agent = ta.agents.OpenRouterAgent(
            model_name=model,
            system_prompt=self.system_template.render(),
            temperature=temperature,
            max_tokens=256,
            **kwargs
        )

    def __call__(self, observation: str) -> str:
        """Process observation and return action number"""
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

        # Render prompt using template
        prompt = self.action_template.render(
            observation=observation,
            choices=choices
        )
        return self.agent(prompt)


# Optional wrapper for more strategic gameplay
class StrategicQuestAgent(ta.AgentWrapper):
    """Adds strategic thinking to quest agent responses"""

    def __init__(self, agent: QuestAgent, debug: bool = False):
        super().__init__(agent)
        self.debug = debug

    def __call__(self, observation: str) -> str:
        # First, analyze the situation
        analysis = self.agent(
            "Analyze this situation and explain your thinking step-by-step instead of choosing an action:\n" + observation
        )
        if self.debug:
            print(f"\nAnalysis: {analysis}")

        # Then make the actual choice
        action = self.agent(f"{observation}\n\nAnalysis:\n{analysis}")
        if self.debug:
            print(f"Chosen action: {action}")

        return action