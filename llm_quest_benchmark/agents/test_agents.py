"""Test agents for environment testing and benchmarking"""
import random
import logging
from typing import Dict, Any, List

from llm_quest_benchmark.agents.base import QuestPlayer


class FirstChoiceAgent(QuestPlayer):
    """Agent that always selects the first available choice"""

    def __init__(self, debug: bool = False):
        self.debug = debug
        self.logger = logging.getLogger(self.__class__.__name__)
        if debug:
            self.logger.setLevel(logging.DEBUG)

    def get_action(self, observation: str, choices: List[Dict[str, str]]) -> str:
        """Always return first choice"""
        if self.debug:
            self.logger.debug(f"Observation: {observation}")
            self.logger.debug(f"Available choices: {len(choices)}")
        return "1"  # Always first choice

    def reset(self) -> None:
        """Nothing to reset"""
        pass


class RandomChoiceAgent(QuestPlayer):
    """Agent that randomly selects from available choices"""

    def __init__(self, seed: int = None, debug: bool = False):
        self.debug = debug
        self.logger = logging.getLogger(self.__class__.__name__)
        if debug:
            self.logger.setLevel(logging.DEBUG)
        self.rng = random.Random(seed) if seed is not None else random.Random()

    def get_action(self, observation: str, choices: List[Dict[str, str]]) -> str:
        """Return random choice"""
        if self.debug:
            self.logger.debug(f"Observation: {observation}")
            self.logger.debug(f"Available choices: {len(choices)}")
        return str(self.rng.randint(1, len(choices)))

    def reset(self) -> None:
        """Nothing to reset"""
        pass