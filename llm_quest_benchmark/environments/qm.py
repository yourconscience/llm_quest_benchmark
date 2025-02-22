"""QM environment for Space Rangers quests"""
from typing import Dict, List, Optional, Tuple, Any
from copy import deepcopy
import logging

from llm_quest_benchmark.utils.choice_mapper import ChoiceMapper
from llm_quest_benchmark.executors.ts_bridge.bridge import QMBridge
from llm_quest_benchmark.dataclasses.state import QMState


class QMPlayerEnv:
    """Environment for playing QM files using TypeScript bridge

    This environment provides a clean interface to Space Rangers quests.
    All game state and logic is handled by the TypeScript bridge, while this class:
    1. Manages the bridge lifecycle
    2. Handles choice mapping between sequential numbers and jump IDs
    3. Formats observations and state
    4. Tracks game history
    """

    def __init__(self, quest_file: str, language: str = "rus", debug: bool = False):
        """Initialize the QMPlayerEnv.

        Args:
            quest_file: Path to QM file
            language: Quest language (rus or eng)
            debug: Enable debug mode
        """
        self.debug = debug
        self.language = language
        self.quest_file = quest_file

        # Initialize logger
        self.logger = logging.getLogger(self.__class__.__name__)
        if self.debug:
            self.logger.setLevel(logging.DEBUG)

        # Initialize bridge
        self.bridge = QMBridge(quest_file, debug=debug)
        self.state_history: List[QMState] = []
        self.choice_mapper: Optional[ChoiceMapper] = None
        self._current_state: Dict[str, Any] = {}  # Internal state storage

    def _format_observation(self, state) -> str:
        """Format observation text from game state"""
        text = state.text

        # Add choices
        text += "\n\nAvailable actions:\n"
        for i, choice in enumerate(state.choices, 1):
            text += f"{i}. {choice['text']}\n"

        return text

    def reset(self) -> str:
        """Reset environment to initial state"""
        initial_bridge_state = self.bridge.start_game()
        self._current_state = {
            'location_id': initial_bridge_state.location_id,
            'text': initial_bridge_state.text,
            'choices': initial_bridge_state.choices,
            'done': initial_bridge_state.game_ended,
            'info': {}
        }
        return self._current_state['text']

    def step(self, action: str) -> Tuple[str, bool, bool, Dict[str, Any]]:
        """Take action in environment and return new state

        Args:
            action: Action to take (choice number or text)

        Returns:
            Tuple of (observation, done, success, info)
        """
        # Take action in bridge
        new_bridge_state = self.bridge.step(action)

        # Update internal state
        self._current_state = {
            'location_id': new_bridge_state.location_id,
            'text': new_bridge_state.text,
            'choices': new_bridge_state.choices,
            'done': new_bridge_state.game_ended,
            'info': {}
        }

        # Return step results - success is when game is done and reward is positive
        success = new_bridge_state.game_ended and new_bridge_state.reward > 0
        return (
            self._current_state['text'],
            self._current_state['done'],
            success,
            self._current_state['info']
        )

    def get_state(self) -> Dict[str, Any]:
        """Get current environment state"""
        return self._current_state.copy()

    def close(self):
        """Clean up resources"""
        if hasattr(self, 'bridge'):
            self.bridge.close()

    @property
    def state(self) -> Dict[str, Any]:
        """Get current state for renderer compatibility"""
        if not self._current_state:
            return {}
        return self._current_state.copy()

    def current_observation(self) -> str:
        """Get current observation for renderer compatibility"""
        if not self._current_state:
            return ""
        return self._format_observation(self._current_state)
