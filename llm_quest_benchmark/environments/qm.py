"""QM environment for Space Rangers quests"""
from typing import Dict, List, Optional, Tuple, Any
from copy import deepcopy

from llm_quest_benchmark.renderers.quest_renderer import QuestRenderer
from llm_quest_benchmark.utils.choice_mapper import ChoiceMapper
from llm_quest_benchmark.executors.ts_bridge.bridge import QMBridge
from llm_quest_benchmark.environments.state import QMState


class QMPlayerEnv:
    """Environment for playing QM files using TypeScript bridge

    This environment provides a clean interface to Space Rangers quests.
    All game state and logic is handled by the TypeScript bridge, while this class:
    1. Manages the bridge lifecycle
    2. Handles choice mapping between sequential numbers and jump IDs
    3. Formats observations and state
    4. Tracks game history and renders state
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

        # Initialize bridge
        self.bridge = QMBridge(quest_file, debug=debug)
        self.state_history: List[QMState] = []
        self.choice_mapper: Optional[ChoiceMapper] = None

        # Initialize renderer
        self.renderer = QuestRenderer(self)

    def _format_observation(self, state) -> str:
        """Format observation text from game state"""
        text = state.text

        # Add choices
        text += "\n\nAvailable actions:\n"
        for i, choice in enumerate(state.choices, 1):
            text += f"{i}. {choice['text']}\n"

        return text

    def reset(self) -> str:
        """Reset the environment to initial state"""
        # Close existing bridge if any
        if hasattr(self, 'bridge'):
            self.bridge.close()

        # Create new bridge and start game
        self.bridge = QMBridge(self.quest_file, debug=self.debug)
        initial_bridge_state = self.bridge.start_game()

        # Create initial state
        initial_state = QMState(
            location_id=initial_bridge_state.location_id,
            text=initial_bridge_state.text,
            choices=initial_bridge_state.choices,
            reward=initial_bridge_state.reward,
            done=initial_bridge_state.game_ended,
            info={}
        )

        # Update choice mapper and history
        self.choice_mapper = ChoiceMapper(initial_state.choices)
        self.state_history = [deepcopy(initial_state)]

        # Add to history and render
        self.renderer.add_to_history(deepcopy(initial_state))
        self.renderer.render()

        return self._format_observation(initial_state)

    def step(self, choice_num: str) -> Tuple[str, float, bool, Dict[str, Any]]:
        """Take a step in the environment

        Args:
            choice_num: String containing the choice number (1-based)

        Returns:
            Tuple of (observation, reward, done, info)
        """
        current_state = self.state_history[-1]
        if current_state.done:
            return self._format_observation(current_state), 0, True, current_state.info

        try:
            # Convert choice number to int
            choice_num_int = int(choice_num)
            if not self.choice_mapper or choice_num_int not in self.choice_mapper:
                raise ValueError(
                    f"Invalid choice {choice_num}. Valid choices: {self.choice_mapper.get_valid_choices() if self.choice_mapper else []}"
                )

            # Take step through bridge
            new_bridge_state = self.bridge.step(choice_num_int)

            # Create new state
            new_state = QMState(
                location_id=new_bridge_state.location_id,
                text=new_bridge_state.text,
                choices=new_bridge_state.choices,
                reward=new_bridge_state.reward,
                done=new_bridge_state.game_ended,
                info={}
            )

            # Update choice mapper and history
            self.choice_mapper = ChoiceMapper(new_state.choices)
            self.state_history.append(deepcopy(new_state))

            # Add to history and render
            self.renderer.add_to_history(deepcopy(new_state))
            self.renderer.render()

            return (
                self._format_observation(new_state),
                new_state.reward,
                new_state.done,
                new_state.info
            )

        except ValueError as e:
            current_state.info['error'] = str(e)
            return (
                self._format_observation(current_state),
                -1,
                False,
                current_state.info
            )

    def close(self):
        """Clean up resources"""
        if hasattr(self, 'bridge'):
            self.bridge.close()

    @property
    def state(self) -> Dict[str, Any]:
        """Get current state for renderer compatibility"""
        current_state = self.state_history[-1] if self.state_history else None
        if not current_state:
            return {}
        return {
            'location_id': current_state.location_id,
            'text': current_state.text,
            'choices': current_state.choices,
            'reward': current_state.reward,
            'done': current_state.done,
            'info': current_state.info
        }

    def current_observation(self) -> str:
        """Get current observation for renderer compatibility"""
        if not self.state_history:
            return ""
        return self._format_observation(self.state_history[-1])
