"""QM environment for Space Rangers quests"""
from typing import Dict, List, Optional, Tuple, Any
from copy import deepcopy
from dataclasses import dataclass

import textarena as ta
from llm_quest_benchmark.renderers.quest_renderer import QuestRenderer
from llm_quest_benchmark.utils.choice_mapper import ChoiceMapper
from llm_quest_benchmark.executors.ts_bridge.bridge import QMBridge


@dataclass
class QMChoice:
    """A choice in a QM location"""
    id: str
    text: str


@dataclass
class QMLocation:
    """A location in a QM file"""
    id: str
    text: str
    choices: List[QMChoice]


@dataclass
class QMGame:
    """A QM game state"""
    locations: Dict[str, QMLocation]
    start_location_id: str


class QMPlayerEnv(ta.Env):
    """Environment for playing QM files using TypeScript bridge

    This environment provides a TextArena-compatible interface to Space Rangers quests.
    All game state and logic is handled by the TypeScript bridge, while this class:
    1. Manages the bridge lifecycle
    2. Handles choice mapping between sequential numbers and jump IDs
    3. Formats observations and state for TextArena compatibility
    4. Tracks game history and renders state
    """

    def __init__(self, quest_file: str, language: str = "rus", debug: bool = False):
        """Initialize the QMPlayerEnv.

        Args:
            quest_file: Path to QM file
            language: Quest language (rus or eng)
            debug: Enable debug mode
        """
        super().__init__()
        self.debug = debug
        self.language = language
        self.quest_file = quest_file

        # Initialize bridge
        self.bridge = QMBridge(quest_file, debug=debug)

        # Start game and get initial state
        initial_state = self.bridge.start_game()

        # Initialize TextArena state
        self.state = {
            'location_id': initial_state.location_id,
            'observation': self._format_observation(initial_state),
            'reward': initial_state.reward,
            'done': initial_state.game_ended,
            'info': {},
            'num_players': 1,  # Single player environment
            'current_player': 0,
            'observations': []
        }

        # Initialize choice mapper
        self.choice_mapper = ChoiceMapper(initial_state.choices)

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
        initial_state = self.bridge.start_game()

        # Update TextArena state
        self.state = {
            'location_id': initial_state.location_id,
            'observation': self._format_observation(initial_state),
            'reward': initial_state.reward,
            'done': initial_state.game_ended,
            'info': {},
            'num_players': 1,
            'current_player': 0,
            'observations': []
        }

        # Update choice mapper
        self.choice_mapper = ChoiceMapper(initial_state.choices)

        # Add to history and render
        self.renderer.add_to_history(deepcopy(self.state))
        self.renderer.render()

        return self.state['observation']

    def step(self, choice_num: str) -> Tuple[str, float, bool, Dict[str, Any]]:
        """Take a step in the environment

        Args:
            choice_num: String containing the choice number (1-based)

        Returns:
            Tuple of (observation, reward, done, info)
        """
        if self.state['done']:
            return self.state['observation'], 0, True, self.info

        try:
            # Convert choice number to jump ID
            choice_num = int(choice_num)
            if choice_num not in self.choice_mapper:
                raise ValueError(f"Invalid choice {choice_num}. Valid choices: {self.choice_mapper.get_valid_choices()}")

            # Take step through bridge
            new_state = self.bridge.step(choice_num)

            # Update TextArena state
            self.state = {
                'location_id': new_state.location_id,
                'observation': self._format_observation(new_state),
                'reward': new_state.reward,
                'done': new_state.game_ended,
                'info': {},
                'num_players': 1,
                'current_player': 0,
                'observations': []
            }

            # Update choice mapper
            self.choice_mapper = ChoiceMapper(new_state.choices)

            # Add to history and render
            self.renderer.add_to_history(deepcopy(self.state))
            self.renderer.render()

            return (
                self.state['observation'],
                self.state['reward'],
                self.state['done'],
                self.state['info']
            )

        except ValueError as e:
            self.state['info']['error'] = str(e)
            return (
                self.state['observation'],
                -1,
                False,
                self.state['info']
            )

    def close(self):
        """Clean up resources"""
        if hasattr(self, 'bridge'):
            self.bridge.close()
