"""Base interface for all renderers"""

import time
from abc import ABC, abstractmethod

from llm_quest_benchmark.schemas.records import QuestTransition


class BaseRenderer(ABC):
    """Base interface for all renderers"""

    def _sleep_for_readability(self, seconds: float = 1.0) -> None:
        """Sleep for specified duration to allow text to be read

        Args:
            seconds (float): Number of seconds to sleep
        """
        time.sleep(seconds)

    @abstractmethod
    def render_game_state(self, transition: QuestTransition) -> None:
        """Render the game state produced by one executed transition

        Args:
            transition (QuestTransition): Executed transition with before/after snapshots
        """
        pass

    def render_title(self) -> None:
        """Optional: Render the game title"""
        pass

    def render_quest_text(self, text: str) -> None:
        """Optional: Render quest text

        Args:
            text (str): Quest text to render
        """
        pass

    def render_choices(self, choices: list[dict[str, str]]) -> None:
        """Optional: Render available choices

        Args:
            choices (List[Dict[str, str]]): List of available choices
        """
        pass

    def render_parameters(self, params: list) -> None:
        """Optional: Render quest parameters

        Args:
            params (list): List of parameters to render
        """
        pass

    def render_error(self, message: str) -> None:
        """Optional: Render error message

        Args:
            message (str): Error message to display
        """
        pass

    def close(self) -> None:
        """Optional: Clean up resources"""
        pass
