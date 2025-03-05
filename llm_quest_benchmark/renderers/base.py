"""Base interface for all renderers"""
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from llm_quest_benchmark.schemas.state import AgentState


class BaseRenderer(ABC):
    """Base interface for all renderers"""

    def _sleep_for_readability(self, seconds: float = 1.0) -> None:
        """Sleep for specified duration to allow text to be read

        Args:
            seconds (float): Number of seconds to sleep
        """
        time.sleep(seconds)

    @abstractmethod
    def render_game_state(self, state: AgentState) -> None:
        """Render the current game state

        Args:
            state (AgentState): Current game state including observation, choices, action, etc.
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

    def render_choices(self, choices: List[Dict[str, str]]) -> None:
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
