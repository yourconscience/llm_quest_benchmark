"""Interactive console player for Space Rangers quests"""
import logging
from typing import List, Dict


class HumanPlayer:
    """Interactive console player that takes input from user"""
    def __init__(self, skip_single: bool = False, debug: bool = False):
        self.skip_single = skip_single
        self.debug = debug
        self.logger = logging.getLogger(__name__)
        if debug:
            self.logger.setLevel(logging.DEBUG)

    def on_game_start(self):
        """Called when game starts"""
        if self.debug:
            self.logger.debug("Starting new game")

    def get_action(self, observation: str, choices: List[Dict[str, str]]) -> str:
        """Get next action from the player

        Args:
            observation: Current game state text
            choices: List of available choices [{id: str, text: str}]

        Returns:
            Choice number as string (1-based)
        """
        if len(choices) == 1 and self.skip_single:
            if self.debug:
                self.logger.debug("Auto-selecting single choice")
            return "1"  # Auto-select if only one choice

        # Print observation and choices
        print("\n" + observation)

        while True:
            try:
                choice = input("Enter choice number (or 'q' to quit): ")
                if choice.lower() == 'q':
                    raise KeyboardInterrupt()

                choice_num = int(choice)
                if 1 <= choice_num <= len(choices):
                    return str(choice_num)

                print(f"Invalid choice. Please enter a number between 1 and {len(choices)}")
            except ValueError:
                print("Invalid input. Please enter a number.")