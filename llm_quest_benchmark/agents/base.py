"""Base classes for quest players (both human and LLM)"""
from abc import ABC, abstractmethod
from typing import Dict, Any


class QuestPlayer(ABC):
    """Abstract base class for quest players"""

    def __init__(self, skip_single: bool = False):
        """Initialize player with skip_single option"""
        self.skip_single = skip_single

    def get_action(self, observation: str, choices: list) -> int:
        """Get action number from observation and choices

        Args:
            observation: Current game text
            choices: List of available choices

        Returns:
            Integer containing the choice number (1-based)

        Raises:
            ValueError: If no choices are provided
        """
        if not choices:
            raise ValueError("No choices provided")

        # Handle single choice skipping if enabled
        if self.skip_single and len(choices) == 1:
            return 1
        return self._get_action_impl(observation, choices)

    @abstractmethod
    def _get_action_impl(self, observation: str, choices: list) -> int:
        """Implementation of action selection logic"""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset player state between episodes"""
        pass

    def on_game_start(self) -> None:
        """Called when game starts"""
        pass

    def on_game_end(self, final_state: Dict[str, Any]) -> None:
        """Called when game ends"""
        pass

    def __str__(self) -> str:
        """String representation of the player"""
        return self.__class__.__name__
