"""QM environment for Space Rangers quests"""
from typing import Dict, List, Optional, Tuple, Any
from copy import deepcopy
import logging
import os
from pathlib import Path

from llm_quest_benchmark.utils.choice_mapper import ChoiceMapper
from llm_quest_benchmark.utils.text_processor import detect_quest_outcome
from llm_quest_benchmark.executors.ts_bridge.bridge import QMBridge
from llm_quest_benchmark.schemas.state import QMState
from llm_quest_benchmark.constants import (
    SYNTHETIC_SUCCESS_LOCATION,
    QUEST_ROOT_DIRECTORY, RECURSIVE_QUEST_SEARCH
)


def find_quest_file(quest_path: str) -> str:
    """Find a quest file in the QUEST_ROOT_DIRECTORY and its subdirectories.
    
    Args:
        quest_path: The path to the quest file, which could be either absolute or relative
    
    Returns:
        The found quest path or the original path if found
        
    Raises:
        FileNotFoundError: If the quest file is not found
    """
    # Use the central quest registry to resolve the path
    from llm_quest_benchmark.core.quest_registry import get_registry
    
    logger = logging.getLogger(__name__)
    registry = get_registry()
    resolved_paths = registry.resolve_quest_path(quest_path)
    
    if not resolved_paths:
        logger.error(f"Quest file not found: {quest_path}")
        raise FileNotFoundError(f"Quest file not found: {quest_path}")
    
    # Return the first matching path
    logger.debug(f"Resolved quest path {quest_path} to {resolved_paths[0]}")
    
    # If multiple paths were found, log a warning
    if len(resolved_paths) > 1:
        logger.warning(f"Multiple quest files matched '{quest_path}'. Using {resolved_paths[0]}.")
        logger.warning(f"Other matches: {', '.join(str(p) for p in resolved_paths[1:])}")
    
    return str(resolved_paths[0])


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
        
        # Initialize logger
        self.logger = logging.getLogger(self.__class__.__name__)
        if self.debug:
            self.logger.setLevel(logging.DEBUG)
            
        try:
            # Try to find the quest file
            self.quest_file = find_quest_file(quest_file)
            if self.debug:
                self.logger.debug(f"Using quest file: {self.quest_file}")
                
            # Initialize bridge
            self.bridge = QMBridge(self.quest_file, language=self.language, debug=debug)
            self.state_history: List[QMState] = []
            self.choice_mapper: Optional[ChoiceMapper] = None
            self._current_state: Dict[str, Any] = {}  # Internal state storage
        except Exception as e:
            self.logger.error(f"Failed to initialize QMPlayerEnv: {e}")
            raise RuntimeError(f"Failed to initialize QMPlayerEnv: {e}")

    @staticmethod
    def _format_params_state(params_state: Any) -> str:
        if not params_state:
            return ""
        if isinstance(params_state, list):
            lines = [str(x).strip() for x in params_state if str(x).strip()]
        else:
            lines = [str(params_state).strip()]
        if not lines:
            return ""
        return "Status:\n" + "\n".join(lines)

    def _compose_observation_text(self, text: str, params_state: Any) -> str:
        base = (text or "").strip()
        params_block = self._format_params_state(params_state)
        if not params_block:
            return base
        if not base:
            return params_block
        return f"{base}\n\n{params_block}"

    def _format_observation(self, state) -> str:
        """Format observation text from game state"""
        if not state:
            return "No state available"

        # Support both QMState-like objects and internal dict state.
        if isinstance(state, dict):
            text = state.get("text") or ""
            params_state = state.get("params_state") or []
            choices = state.get("choices") or []
        else:
            text = getattr(state, "text", "") or ""
            params_state = getattr(state, "params_state", []) or []
            choices = getattr(state, "choices", []) or []

        text = self._compose_observation_text(text, params_state)

        # Add choices if available
        if choices:
            text += "\n\nAvailable actions:\n"
            for i, choice in enumerate(choices, 1):
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
                'params_state': initial_bridge_state.params_state,
                'choices': initial_bridge_state.choices,
                'reward': initial_bridge_state.reward,
                'done': initial_bridge_state.game_ended,
                'info': {}
            }

            if not self._current_state['choices']:
                raise RuntimeError("No valid choices in initial state")

            return self._compose_observation_text(
                self._current_state["text"], self._current_state.get("params_state")
            )
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
            
        # Check for patterns that might indicate an infinite loop
        # This is a general solution that works for any quest that might get stuck
        if len(self.bridge.state_history) > 30:  # Only check after a reasonable number of steps
            # Get the current state text
            current_text = self._current_state.get('text', '')
            
            # Check for repeating daily routine patterns (like in Prison.qm)
            repeat_day_pattern_count = 0
            repeat_text_fragments = 0
            
            # Check last 10 states for repetition
            text_fragments = []
            for state in self.bridge.state_history[-10:]:
                if state.text:
                    # Add first 20 chars of each state text for comparison
                    text_fragment = state.text[:20].strip()
                    text_fragments.append(text_fragment)
                    
                    # Specific check for daily pattern (appears in Prison.qm)
                    if "Наступил новый день" in state.text:
                        repeat_day_pattern_count += 1
            
            # Count how many times each fragment appears
            from collections import Counter
            fragment_counts = Counter(text_fragments)
            
            # If any single text fragment appears 5+ times in the last 10 states
            # or if we see 5+ daily routine messages
            if any(count >= 5 for count in fragment_counts.values()) or repeat_day_pattern_count >= 5:
                self.logger.warning(f"Detected potential infinite loop after {len(self.bridge.state_history)} steps")

                synthetic_text = (
                    current_text
                    + "\n\n[Forced stop: repetitive state loop detected before terminal quest outcome]"
                )

                forced_info = {"forced_completion": True, "reason": "infinite_loop_detected"}
                self._current_state = {
                    "location_id": self._current_state.get("location_id", "unknown"),
                    "text": synthetic_text,
                    "params_state": self._current_state.get("params_state", []),
                    "choices": [],
                    "reward": self._current_state.get("reward", 0.0),
                    "done": True,
                    "info": forced_info,
                }

                # Loop detection is a non-terminal fallback signal, not a quest success.
                return (
                    self._compose_observation_text(
                        self._current_state["text"], self._current_state.get("params_state")
                    ),
                    True,
                    False,
                    forced_info,
                )

        try:
            # Take action in bridge
            new_bridge_state = self.bridge.step(action)
            if not new_bridge_state:
                raise RuntimeError("Failed to get new state from bridge")

            # Update internal state
            self._current_state = {
                'location_id': new_bridge_state.location_id,
                'text': new_bridge_state.text,
                'params_state': new_bridge_state.params_state,
                'choices': new_bridge_state.choices,
                'reward': new_bridge_state.reward,
                'done': new_bridge_state.game_ended,
                'info': {}
            }

            # Determine success based on multiple factors
            success = False
            
            # Handle special case for synthetic success location
            if new_bridge_state.location_id == SYNTHETIC_SUCCESS_LOCATION and new_bridge_state.game_ended:
                success = True
                self.logger.info("Quest ended successfully with synthetic success marker")
            
            # Check if there's a positive reward value
            elif new_bridge_state.game_ended and new_bridge_state.reward > 0:
                success = True
                self.logger.info("Quest ended successfully based on reward value")
            
            # If the quest ended but wasn't determined successful yet, check text content using our utility
            elif new_bridge_state.game_ended and new_bridge_state.text:
                # Use our dedicated outcome detection utility
                success, reward, reason = detect_quest_outcome(new_bridge_state.text)
                
                # Log the result
                if success:
                    self.logger.info(f"Quest ended successfully based on {reason}")
                    if reward > 0:
                        self.logger.info(f"Detected reward: {reward}")
                elif reason != "no_indicators":
                    self.logger.info(f"Quest failed based on {reason}")

            if new_bridge_state.game_ended:
                # Just log the essential info at INFO level for better visibility
                self.logger.info(f"Game ended with reward: {new_bridge_state.reward}, success: {success}")

            return (
                self._compose_observation_text(
                    self._current_state["text"], self._current_state.get("params_state")
                ),
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
