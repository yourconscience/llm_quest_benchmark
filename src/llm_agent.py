"""
LLM-powered agent for Space Rangers quests using TextArena's agent system
"""
import textarena as ta
from typing import Optional

QUEST_PROMPT_TEMPLATE = """You are playing a Space Rangers text quest. You will be presented with a location description and a list of available actions. Your goal is to complete the quest successfully.

The game will present you with numbered choices. To select an action, respond with just the number of your chosen action.

Example observation:
Trading Station
You find yourself at a bustling trading station. Several merchants eye you suspiciously.

Available actions:
1. Approach the weapon merchant
2. Visit the ship upgrades shop
3. Leave the station

Example response:
2

Current observation:
{observation}

Choose your action (respond with just the number):"""

class QuestAgent(ta.Agent):
    """TextArena agent specialized for Space Rangers quests"""

    def __init__(
        self,
        model: str = "claude-3.5-sonnet",
        system_prompt: Optional[str] = QUEST_PROMPT_TEMPLATE,
        temperature: float = 0.4,
        **kwargs
    ):
        super().__init__()
        self.agent = ta.agents.OpenRouterAgent(
            model_name=model,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=256,
            **kwargs
        )

    def __call__(self, observation: str) -> str:
        """Process observation and return action number"""
        return self.agent(observation)


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