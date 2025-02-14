"""Test player implementations for automated testing"""
import random
import logging
from typing import List, Dict


class FirstChoicePlayer:
    """Test player that always selects the first available choice"""
    def __init__(self, skip_single: bool = False, debug: bool = False):
        self.skip_single = skip_single
        self.debug = debug
        self.logger = logging.getLogger(__name__)
        if debug:
            self.logger.setLevel(logging.DEBUG)

    def on_game_start(self):
        """Called when game starts"""
        if self.debug:
            self.logger.debug("Starting new game with FirstChoicePlayer")

    def get_action(self, observation: str, choices: List[Dict[str, str]]) -> str:
        """Always returns "1" for first choice"""
        if self.debug:
            self.logger.debug(f"Selecting first choice from {len(choices)} options")
            self.logger.debug(f"Current state:\n{observation}")
        return "1"


class RandomChoicePlayer:
    """Test player that randomly selects from available choices"""
    def __init__(self, skip_single: bool = False, debug: bool = False):
        self.skip_single = skip_single
        self.debug = debug
        self.logger = logging.getLogger(__name__)
        if debug:
            self.logger.setLevel(logging.DEBUG)

    def on_game_start(self):
        """Called when game starts"""
        if self.debug:
            self.logger.debug("Starting new game with RandomChoicePlayer")

    def get_action(self, observation: str, choices: List[Dict[str, str]]) -> str:
        """Returns random choice number"""
        choice = str(random.randint(1, len(choices)))
        if self.debug:
            self.logger.debug(f"Selected choice {choice} from {len(choices)} options")
            self.logger.debug(f"Current state:\n{observation}")
        return choice