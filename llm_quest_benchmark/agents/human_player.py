"""Interactive console player for Space Rangers quests"""
import logging
from typing import List, Dict, Any

from llm_quest_benchmark.agents.base import QuestPlayer


class HumanPlayer(QuestPlayer):
    """Interactive console player that takes input from user"""
    def __init__(self, skip_single: bool = False, **kwargs):
        super().__init__(skip_single=skip_single)
        self.logger = logging.getLogger(__name__)

    def _get_action_impl(self, observation: str, choices: list) -> int:
        """Implementation of action selection logic"""

        while True:
            try:
                choice = input()
                if choice.lower() == 'q':
                    raise KeyboardInterrupt()

                choice_num = int(choice)
                if 1 <= choice_num <= len(choices):
                    return choice_num

                print(f"Invalid choice. Please enter a number between 1 and {len(choices)}")
            except ValueError:
                print("Invalid input. Please enter a number.")

    def reset(self) -> None:
        """Reset player state between episodes"""
        pass

    def on_game_start(self) -> None:
        """Called when game starts"""
        pass

    def on_game_end(self, final_state: Dict[str, Any]) -> None:
        """Called when game ends"""
        pass