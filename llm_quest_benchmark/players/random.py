"""Random player for testing quests"""

import logging
import random

from llm_quest_benchmark.players.base import QuestPlayer


class RandomPlayer(QuestPlayer):
    """Player that randomly selects from available choices.

    Used for testing quests and finding edge cases.
    """

    harness_name = "random_choice"

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
        # The seed is a material knob, so it belongs in the harness identifier.
        self.harness_name = f"random_choice_{seed}" if seed is not None else "random_choice"
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

    def rebuild_from_transitions(self, transitions) -> None:
        """Advance the RNG past the decisions a resumed run already made.

        A seeded random policy is only deterministic if its stream position is
        restored, so each recorded decision consumes exactly the draw it
        originally consumed. Auto-selected single choices never consumed one.
        """
        for transition in transitions:
            if not transition.action.is_choose:
                continue
            choices = transition.before.choices
            if self.skip_single and len(choices) == 1:
                continue
            self.rng.randint(1, len(choices))
