"""Random agent for testing quests"""
import random
import logging
from typing import Dict, List

from llm_quest_benchmark.agents.base import QuestPlayer


class RandomAgent(QuestPlayer):
    """Agent that randomly selects from available choices.
    Used for testing quests and finding edge cases."""

    def __init__(self, seed: int = None, **kwargs):
        """Initialize random agent.

        Args:
            seed (int, optional): Random seed for reproducibility. Defaults to None.
        """
        super().__init__(skip_single=True)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.rng = random.Random(seed)

    def _get_action_impl(self, observation: str, choices: List[Dict[str, str]]) -> int:
        """Return random choice from available options.

        Args:
            observation (str): Current game state observation
            choices (List[Dict[str, str]]): Available choices

        Returns:
            int: Selected choice number (1-based)
        """
        return self.rng.randint(1, len(choices))

    def reset(self) -> None:
        """Reset agent state - nothing to reset for random agent"""
        pass