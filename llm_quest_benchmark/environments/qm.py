"""QM environment for Space Rangers quests"""
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from llm_quest_benchmark.renderers.quest_renderer import QuestRenderer


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


class QMPlayerEnv:
    """Environment for playing QM files"""

    def __init__(self, game: QMGame):
        self.game = game
        self.current_location_id = None
        self.renderer = QuestRenderer(self)
        self.done = False
        self.reward = 0
        self.info = {}

    def _get_location_description(self) -> str:
        """Get the current location description with choices"""
        location = self.game.locations[self.current_location_id]
        desc = location.text + "\n\nChoices:\n"
        for choice in location.choices:
            desc += f"- {choice.text}\n"
        return desc

    def reset(self) -> str:
        """Reset the environment to initial state"""
        self.current_location_id = self.game.start_location_id
        self.done = False
        self.reward = 0
        self.info = {}

        # Get initial observation
        observation = self._get_location_description()

        # Add to history and render
        self.renderer.add_to_history({
            'location_id': self.current_location_id,
            'observation': observation
        })
        self.renderer.render()

        return observation

    def step(self, choice_id: str) -> Tuple[str, float, bool, Dict[str, Any]]:
        """Take a step in the environment"""
        if self.done:
            return self._get_location_description(), 0, True, self.info

        # Validate choice
        location = self.game.locations[self.current_location_id]
        valid_choices = [c.id for c in location.choices]

        if choice_id not in valid_choices:
            self.info['error'] = f'Invalid choice {choice_id}. Valid choices: {valid_choices}'
            return self._get_location_description(), -1, False, self.info

        # Update state
        self.current_location_id = choice_id
        observation = self._get_location_description()

        # Check if we're done
        self.done = len(self.game.locations[choice_id].choices) == 0
        self.reward = 1 if self.done else 0

        # Add to history and render
        self.renderer.add_to_history({
            'location_id': self.current_location_id,
            'observation': observation,
            'reward': self.reward,
            'done': self.done
        })
        self.renderer.render()

        return observation, self.reward, self.done, self.info
