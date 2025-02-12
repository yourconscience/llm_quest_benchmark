"""Bridge between Python and TypeScript QM engine"""
import json
import logging
import subprocess
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class GameState:
    """Formatted game state for environment consumption"""
    location_id: str
    text: str
    choices: List[Dict[str, str]]  # [{id: str, text: str}]
    game_ended: bool
    params: Dict[str, Any]
    reward: float

    @classmethod
    def from_raw_state(cls, raw_state: Dict[str, Any]) -> 'GameState':
        """Create GameState from raw TypeScript state"""
        state = raw_state['state']
        saving = raw_state['saving']

        # Clean QM tags from text
        text = (state['text']
               .replace('<clr>', '')
               .replace('<clrEnd>', '')
               .replace('\r\n', '\n'))

        return cls(
            location_id=str(saving['locationId']),
            text=text,
            choices=[{
                'id': str(c['jumpId']),
                'text': c['text'].replace('<clr>', '').replace('<clrEnd>', '')
            } for c in state['choices']],
            game_ended=len(state['choices']) == 0,
            params=saving['paramValues'],
            reward=1.0 if state.get('gameState') == 'win' else 0.0
        )


class QMBridge:
    """Handles communication with TypeScript QM engine"""

    def __init__(self, quest_file: str, debug: bool = False):
        """Initialize bridge with quest file path"""
        self.quest_file = Path(quest_file).resolve()
        self.debug = debug
        self.process = None
        self.parser_script = Path(__file__).parent / "consoleplayer.ts"
        self.state_history: List[GameState] = []

    def parse_quest(self) -> Dict[str, Any]:
        """Parse quest file and return raw QM structure"""
        cmd = ["node", "-r", "ts-node/register", str(self.parser_script), str(self.quest_file), "--parse"]

        if self.debug:
            logger.debug(f"Running parser command: {' '.join(cmd)}")

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
            if self.debug:
                logger.debug(f"Raw parser output: {proc.stdout[:500]}...")

            return json.loads(proc.stdout)

        except subprocess.CalledProcessError as e:
            logger.error(f"Node parser error:\n{e.stderr}")
            raise RuntimeError(f"Node parser error:\n{e.stderr}")
        except Exception as e:
            logger.error(f"Failed to parse QM data: {str(e)}")
            raise ValueError(f"Failed to parse QM data: {str(e)}")

    def start_game(self) -> GameState:
        """Start game process and return initial state"""
        cmd = ["node", "-r", "ts-node/register", str(self.parser_script), str(self.quest_file)]

        if self.debug:
            logger.debug(f"Starting game process: {' '.join(cmd)}")

        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Read initial state
            initial_raw = self.process.stdout.readline()
            if self.debug:
                logger.debug(f"Initial raw state: {initial_raw}")

            initial_state = GameState.from_raw_state(json.loads(initial_raw))
            self.state_history.append(initial_state)
            return initial_state

        except Exception as e:
            logger.error(f"Failed to start game: {str(e)}")
            raise RuntimeError(f"Failed to start game: {str(e)}")

    def get_current_state(self) -> GameState:
        """Get current game state"""
        if not self.process:
            raise RuntimeError("Game not started")

        try:
            self.process.stdin.write("get_state\n")
            self.process.stdin.flush()
            raw_state = json.loads(self.process.stdout.readline())
            return GameState.from_raw_state(raw_state)
        except Exception as e:
            logger.error(f"Failed to get current state: {str(e)}")
            raise RuntimeError(f"Failed to get current state: {str(e)}")

    def validate_choice(self, choice_num: int) -> Optional[str]:
        """Validate choice number and return corresponding jump ID"""
        current_state = self.state_history[-1] if self.state_history else self.get_current_state()

        if not (1 <= choice_num <= len(current_state.choices)):
            valid_choices = list(range(1, len(current_state.choices) + 1))
            raise ValueError(
                f"Invalid choice {choice_num}. Valid choices: {valid_choices}\n"
                f"Current state: {json.dumps(current_state.__dict__, indent=2)}"
            )

        return current_state.choices[choice_num - 1]['id']

    def step(self, choice_num: int) -> GameState:
        """Take a step in the game with choice number (1-based)"""
        if not self.process:
            raise RuntimeError("Game not started")

        try:
            # Validate and map choice
            jump_id = self.validate_choice(choice_num)

            if self.debug:
                logger.debug(f"Sending jump ID: {jump_id}")

            # Send jump ID to process
            self.process.stdin.write(f"{jump_id}\n")
            self.process.stdin.flush()

            # Read response
            response = self.process.stdout.readline()
            if self.debug:
                logger.debug(f"Raw response: {response}")

            # Parse and store new state
            new_state = GameState.from_raw_state(json.loads(response))
            self.state_history.append(deepcopy(new_state))
            return new_state

        except ValueError as e:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"Failed to process step: {str(e)}")
            raise RuntimeError(f"Failed to process step: {str(e)}")

    def get_debug_state(self) -> str:
        """Get formatted debug state"""
        current_state = self.state_history[-1] if self.state_history else self.get_current_state()
        return (
            f"Location: {current_state.location_id}\n"
            f"Game ended: {current_state.game_ended}\n"
            f"Reward: {current_state.reward}\n"
            f"Choices:\n" +
            "\n".join(f"{i+1}. {c['text']} (id: {c['id']})"
                     for i, c in enumerate(current_state.choices))
        )

    def close(self):
        """Clean up game process"""
        if self.process:
            self.process.terminate()
            self.process = None