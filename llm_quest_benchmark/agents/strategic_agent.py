"""Strategic agent decorator that adds analysis capabilities"""
from typing import Dict, Any

from llm_quest_benchmark.agents.base import QuestPlayer


class StrategicAgent(QuestPlayer):
    """Decorator that adds strategic thinking to any quest player"""

    def __init__(self, base_agent: QuestPlayer, debug: bool = False):
        self.agent = base_agent
        self.debug = debug
        self.history = []

    def get_action(self, observation: str, choices: list) -> str:
        """Add strategic analysis before making choice"""
        # First, analyze the situation
        if hasattr(self.agent, 'llm'):
            analysis = self.agent.llm(
                "Analyze this situation and explain your thinking step-by-step instead of choosing an action:\n"
                + observation)
            if self.debug:
                print(f"\nAnalysis: {analysis}")

            # Store analysis in history
            self.history.append({
                'observation': observation,
                'analysis': analysis
            })

            # Then make the actual choice with analysis context
            return self.agent.get_action(
                f"{observation}\n\nAnalysis:\n{analysis}",
                choices
            )
        else:
            # If agent doesn't have LLM capability, just pass through
            return self.agent.get_action(observation, choices)

    def reset(self) -> None:
        """Reset both strategic and base agent state"""
        self.history = []
        self.agent.reset()

    def on_game_start(self) -> None:
        """Pass through to base agent"""
        self.agent.on_game_start()

    def on_game_end(self, final_state: Dict[str, Any]) -> None:
        """Pass through to base agent and log analysis history"""
        self.agent.on_game_end(final_state)
        if self.debug:
            print("\nFinal Analysis History:")
            for entry in self.history:
                print(f"\nObservation: {entry['observation']}")
                print(f"Analysis: {entry['analysis']}")