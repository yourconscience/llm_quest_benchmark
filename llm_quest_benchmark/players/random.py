"""Random player for testing quests"""

import logging
import random

from llm_quest_benchmark.players.base import QuestPlayer


class RandomPlayer(QuestPlayer):
    """Player that randomly selects from available choices.

    Used for testing quests and finding edge cases.
    """

    def __init__(self, seed: int = None, debug: bool = False, skip_single: bool = False):
        """Initialize random player.

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
        # Keep the persisted identifier stable for existing result artifacts.
        self.agent_id = f"random_{seed}" if seed is not None else "random"

    def _get_action_impl(self, observation: str, choices: list[dict[str, str]]) -> int:
        """Return random choice from available options.

        Args:
            observation (str): Current game state observation
            choices (List[Dict[str, str]]): Available choices

        Returns:
            int: Selected choice number (1-based)
        """
        if self.debug:
            self.logger.debug(f"Observation: {observation}")
            self.logger.debug(f"Available choices: {len(choices)}")
        return self.rng.randint(1, len(choices))

    def reset(self) -> None:
        """Reset player state; nothing to reset for random choice."""
        pass
