"""QM environment for Space Rangers quests"""
from typing import Dict, List, Optional, Tuple, Any
from copy import deepcopy
import logging

from llm_quest_benchmark.utils.choice_mapper import ChoiceMapper
from llm_quest_benchmark.executors.ts_bridge.bridge import QMBridge
from llm_quest_benchmark.schemas.state import QMState


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

        try:
            # Initialize bridge
            self.bridge = QMBridge(quest_file, debug=debug)
            self.state_history: List[QMState] = []
            self.choice_mapper: Optional[ChoiceMapper] = None
            self._current_state: Dict[str, Any] = {}  # Internal state storage
        except Exception as e:
            self.logger.error(f"Failed to initialize QMPlayerEnv: {e}")
            raise RuntimeError(f"Failed to initialize QMPlayerEnv: {e}")

    def _format_observation(self, state) -> str:
        """Format observation text from game state"""
        if not state:
            return "No state available"

        text = state.text or ""

        # Add choices if available
        if state.choices:
            text += "\n\nAvailable actions:\n"
            for i, choice in enumerate(state.choices, 1):
                text += f"{i}. {choice['text']}\n"

        return text

    def reset(self) -> str:
        """Reset environment to initial state"""
        try:
            initial_bridge_state = self.bridge.start_game()
            if not initial_bridge_state:
                raise RuntimeError("Failed to get initial state from bridge")

            self._current_state = {
                'location_id': initial_bridge_state.location_id,
                'text': initial_bridge_state.text,
                'choices': initial_bridge_state.choices,
                'done': initial_bridge_state.game_ended,
                'info': {}
            }

            if not self._current_state['choices']:
                raise RuntimeError("No valid choices in initial state")

            return self._current_state['text']
        except Exception as e:
            self.logger.error(f"Failed to reset environment: {e}")
            self.bridge.close()  # Clean up on error
            raise RuntimeError(f"Failed to reset environment: {e}")

    def step(self, action: str) -> Tuple[str, bool, bool, Dict[str, Any]]:
        """Take action in environment and return new state

        Args:
            action: Action to take (choice number or text)

        Returns:
            Tuple of (observation, done, success, info)
        """
        if not self._current_state:
            raise RuntimeError("Environment not initialized - call reset() first")

        try:
            # Take action in bridge
            new_bridge_state = self.bridge.step(action)
            if not new_bridge_state:
                raise RuntimeError("Failed to get new state from bridge")

            # Update internal state
            self._current_state = {
                'location_id': new_bridge_state.location_id,
                'text': new_bridge_state.text,
                'choices': new_bridge_state.choices,
                'done': new_bridge_state.game_ended,
                'info': {}
            }

            # Determine success based solely on reward value
            success = new_bridge_state.game_ended and new_bridge_state.reward > 0

            if new_bridge_state.game_ended:
                self.logger.debug(f"Game ended with text: {new_bridge_state.text}")
                self.logger.debug(f"Game ended with reward: {new_bridge_state.reward}")
                self.logger.debug(f"Success determined as: {success}")
                self.logger.debug(f"Game state: {new_bridge_state.__dict__}")

            return (
                self._current_state['text'],
                self._current_state['done'],
                success,
                self._current_state['info']
            )
        except Exception as e:
            self.logger.error(f"Failed to take step: {e}")
            self.bridge.close()  # Clean up on error
            raise RuntimeError(f"Failed to take step: {e}")

    def get_state(self) -> Dict[str, Any]:
        """Get current environment state"""
        if not self._current_state:
            raise RuntimeError("Environment not initialized - call reset() first")
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
