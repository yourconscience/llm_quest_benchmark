"""Base classes for quest players (both human and LLM)"""
from abc import ABC, abstractmethod
from typing import Dict, Any


class QuestPlayer(ABC):
    """Abstract base class for quest players"""

    @abstractmethod
    def get_action(self, observation: str, choices: list) -> str:
        """Get action number from observation and choices

        Args:
            observation: Current game text
            choices: List of available choices

        Returns:
            String containing the choice number (1-based)
        """
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