"""Random agent for testing quests"""
import random
import logging
from typing import Dict, List

from llm_quest_benchmark.agents.base import QuestPlayer


class RandomAgent(QuestPlayer):
    """Agent that randomly selects from available choices.
    Used for testing quests and finding edge cases."""

    def __init__(self, seed: int = None, debug: bool = False, skip_single: bool = False):
        """Initialize random agent.

        Args:
            seed (int, optional): Random seed for reproducibility. Defaults to None.
            debug (bool, optional): Enable debug logging. Defaults to False.
            skip_single (bool, optional): Auto-select single choices. Defaults to False.
        """
        super().__init__(skip_single=skip_single)
        self.debug = debug
        self.logger = logging.getLogger(self.__class__.__name__)
        if debug:
            self.logger.setLevel(logging.DEBUG)
        self.rng = random.Random(seed)

    def _get_action_impl(self, observation: str, choices: List[Dict[str, str]]) -> str:
        """Return random choice from available options.

        Args:
            observation (str): Current game state observation
            choices (List[Dict[str, str]]): Available choices

        Returns:
            str: Selected choice number as string
        """
        if self.debug:
            self.logger.debug(f"Observation: {observation}")
            self.logger.debug(f"Available choices: {len(choices)}")
        return str(self.rng.randint(1, len(choices)))

    def reset(self) -> None:
        """Reset agent state - nothing to reset for random agent"""
        pass