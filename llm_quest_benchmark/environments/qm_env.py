"""TextArena environment for Space Rangers quests"""
from pathlib import Path
from typing import Any, Dict

import textarena as ta

from llm_quest_benchmark.environments.qm import parse_qm


class QMPlayerEnv(ta.Env):
    """TextArena environment for Space Rangers quests"""

    def __init__(self, qm_file: str, max_steps: int = 100, **kwargs):
        super().__init__()
        self.qm_file = Path(qm_file)

        # Parse QM file
        self.qm_data = parse_qm(str(self.qm_file))

        # Initialize TextArena state
        self.state = ta.State(num_players=1, max_turns=max_steps, role_mapping={0: "Player"})

        # Track current location
        self.current_loc_id = self.qm_data.start_id

        # Add metrics tracking
        self.metrics = {
            'steps_taken': 0,
            'valid_actions': 0,
            'invalid_actions': 0,
            'quest_completed': False,
            'error_log': []
        }

    def _get_location_description(self) -> str:
        """Get current location description with available actions"""
        loc = self.qm_data.get_location(self.current_loc_id)
        desc = f"{loc.text}\n\nAvailable actions:\n"
        for i, choice in enumerate(loc.choices, 1):
            desc += f"{i}. {choice.text}\n"
        return desc

    def current_observation(self) -> str:
        """Get current observation for rendering"""
        return self._get_location_description()

    def reset(self, seed: int = None) -> dict:
        """Reset to initial state"""
        if seed is not None:
            import random
            random.seed(seed)

        self.current_loc_id = self.qm_data.start_id

        self.state.reset(
            game_state={"description": self._get_location_description()},
            player_prompt_function=lambda **kwargs: kwargs['game_state'].get("description", "")
        )
        return self.state.observations

    def step(self, action: str):
        """Execute action and return new state"""
        self.metrics['steps_taken'] += 1

        try:
            # Convert action to choice index
            choice_idx = int(action.strip()) - 1
            loc = self.qm_data.get_location(self.current_loc_id)

            if not (0 <= choice_idx < len(loc.choices)):
                raise ValueError("Invalid choice index")

            # Execute choice
            choice = loc.choices[choice_idx]
            self.current_loc_id = choice.jumpId

            # Update state
            self.state.add_observation(from_id=ta.GAME_ID,
                                       to_id=0,
                                       message=self._get_location_description(),
                                       for_logging=True)

            # Check if quest ended (no more choices)
            new_loc = self.qm_data.get_location(self.current_loc_id)
            done = len(new_loc.choices) == 0
            reward = 1.0 if done else 0.0

            self.metrics['valid_actions'] += 1
            return self.state.observations, {0: reward}, done, {}

        except (ValueError, IndexError) as e:
            self.metrics['invalid_actions'] += 1
            self.metrics['error_log'].append({'step': self.metrics['steps_taken'], 'error': str(e)})
            self.state.add_observation(from_id=ta.GAME_ID,
                                       to_id=0,
                                       message=f"Invalid action: {action}. Error: {str(e)}",
                                       for_logging=True)
            return self.state.observations, {0: -1}, True, {"error": str(e)}

    def render(self, mode: str = "human") -> None:
        """Render current game state"""
        print("\n=== Current Location ===")
        print(self._get_location_description())

    def get_metrics(self) -> Dict[str, Any]:
        """Return copy of metrics for analysis"""
        return self.metrics.copy()
