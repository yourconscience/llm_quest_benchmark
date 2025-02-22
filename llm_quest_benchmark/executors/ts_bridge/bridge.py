"""TypeScript bridge for QM file parsing and execution"""
import logging
import json
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Optional, Any

from llm_quest_benchmark.dataclasses.bridge import QMBridgeState

logger = logging.getLogger(__name__)


class QMBridge:
    """Bridge to TypeScript QM parser and executor"""

    def __init__(self, quest_file: str, debug: bool = False):
        """Initialize bridge with quest file path"""
        self.quest_file = Path(quest_file).resolve()
        self.debug = debug
        self.process = None
        self.parser_script = Path(__file__).parent / "consoleplayer.ts"
        self.state_history: List[QMBridgeState] = []

    def parse_quest_locations(self) -> Dict[str, Any]:
        """Parse quest file and return metadata including locations and start location"""
        cmd = ["node", "-r", "ts-node/register", str(self.parser_script), str(self.quest_file), "--parse"]

        if self.debug:
            logger.debug(f"Running parser command: {' '.join(cmd)}")

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
            if self.debug:
                logger.debug(f"Raw parser output: {proc.stdout[:500]}...")

            try:
                from json_repair import repair_json
                # Clean the output - remove any non-JSON text before/after
                output = proc.stdout.strip()
                if '{' in output:
                    output = output[output.find('{'):output.rfind('}')+1]
                repaired_json = repair_json(output)
                qm_data = json.loads(repaired_json)
            except ImportError:
                # Fallback to direct JSON parsing if json-repair not available
                qm_data = json.loads(proc.stdout)

            metadata = qm_data.get('metadata', {})
            total_locations = len(metadata.get('locations', []))
            start_location = metadata.get('startLocationId', 0)

            if self.debug:
                logger.debug(f"Parsed metadata: start location {start_location}, total locations: {total_locations}")

            return {
                'start_location_id': start_location,
                'locations': metadata.get('locations', []),
                'total_locations': total_locations if total_locations > 0 else 20  # Default fallback for progress bar
            }

        except subprocess.CalledProcessError as e:
            logger.error(f"Node parser error:\n{e.stderr}")
            # Return default values instead of raising
            return {
                'start_location_id': 0,
                'locations': [],
                'total_locations': 20  # Default fallback for progress bar
            }
        except Exception as e:
            logger.error(f"Failed to parse QM data: {str(e)}")
            # Return default values instead of raising
            return {
                'start_location_id': 0,
                'locations': [],
                'total_locations': 20  # Default fallback for progress bar
            }

    def start_game(self) -> QMBridgeState:
        """Start game process and return initial state"""
        cmd = ["node", "-r", "ts-node/register", str(self.parser_script), str(self.quest_file)]

        if self.debug:
            logger.debug(f"Starting game process: {' '.join(cmd)}")

        try:
            # Close any existing process
            if self.process:
                self.close()

            # Start new process
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1  # Line buffered
            )

            # Read initial state
            initial_raw = self._read_response()
            if not initial_raw:
                raise RuntimeError("No initial state received from TypeScript bridge")

            # Parse response and extract state
            response = json.loads(initial_raw)
            if 'state' not in response:
                raise RuntimeError("Invalid response format: missing 'state' field")

            state = response['state']
            initial_state = QMBridgeState(
                location_id=str(response['saving']['locationId']),
                text=state['text'],
                choices=[{'id': str(c['jumpId']), 'text': c['text']} for c in state['choices'] if c['active']],
                reward=0.0,  # Initial state has no reward
                game_ended=state['gameState'] != 'running'
            )

            self.state_history.append(initial_state)
            return initial_state

        except Exception as e:
            logger.error(f"Failed to start game: {str(e)}")
            self.close()  # Clean up on error
            raise RuntimeError(f"Failed to start game: {str(e)}")

    def get_current_state(self) -> QMBridgeState:
        """Get current game state"""
        if not self.process:
            raise RuntimeError("Game not started")

        try:
            self.process.stdin.write("get_state\n")
            self.process.stdin.flush()

            response = self._read_response()
            if not response:
                raise RuntimeError("No response received from TypeScript bridge")

            # Parse response and extract state
            response_data = json.loads(response)
            if 'state' not in response_data:
                raise RuntimeError("Invalid response format: missing 'state' field")

            state = response_data['state']
            return QMBridgeState(
                location_id=str(response_data['saving']['locationId']),
                text=state['text'],
                choices=[{'id': str(c['jumpId']), 'text': c['text']} for c in state['choices'] if c['active']],
                reward=0.0,  # Get reward from game state if available
                game_ended=state['gameState'] != 'running'
            )

        except Exception as e:
            logger.error(f"Failed to get current state: {str(e)}")
            self.close()  # Clean up on error
            raise RuntimeError(f"Failed to get current state: {str(e)}")

    def validate_choice(self, choice_num: int) -> Optional[str]:
        """Validate choice number and return corresponding jump ID"""
        current_state = self.state_history[-1] if self.state_history else self.get_current_state()

        # Convert choice_num to int to ensure type safety
        try:
            choice_num = int(choice_num)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid choice number: {choice_num}")

        num_choices = len(current_state.choices)
        if not (1 <= choice_num <= num_choices):
            valid_choices = list(range(1, num_choices + 1))
            raise ValueError(
                f"Invalid choice {choice_num}. Valid choices: {valid_choices}\n"
                f"Current state: {json.dumps(current_state.__dict__, indent=2)}"
            )

        return current_state.choices[choice_num - 1]['id']

    def step(self, choice_num: int) -> QMBridgeState:
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
            response = self._read_response()
            if not response:
                raise RuntimeError("No response received from TypeScript bridge")

            # Parse response and extract state
            response_data = json.loads(response)
            if 'state' not in response_data:
                raise RuntimeError("Invalid response format: missing 'state' field")

            state = response_data['state']
            new_state = QMBridgeState(
                location_id=str(response_data['saving']['locationId']),
                text=state['text'],
                choices=[{'id': str(c['jumpId']), 'text': c['text']} for c in state['choices'] if c['active']],
                reward=1.0 if state['gameState'] == 'win' else 0.0,  # Win state gives positive reward
                game_ended=state['gameState'] != 'running'
            )

            self.state_history.append(deepcopy(new_state))
            return new_state

        except ValueError as e:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"Failed to process step: {str(e)}")
            self.close()  # Clean up on error
            raise RuntimeError(f"Failed to process step: {str(e)}")

    def _read_response(self) -> str:
        """Read response from TypeScript bridge with error handling"""
        if not self.process:
            raise RuntimeError("Game process not started")

        try:
            response = ""
            json_depth = 0
            in_json = False

            while True:
                # Check if process is still alive
                if self.process.poll() is not None:
                    stderr = self.process.stderr.read()
                    raise RuntimeError(f"Game process terminated unexpectedly. stderr: {stderr}")

                line = self.process.stdout.readline()
                if not line:
                    break

                # Skip non-JSON output
                if not in_json and '{' in line:
                    in_json = True
                    response = line[line.find('{'):]
                elif in_json:
                    response += line

                if in_json:
                    # Count JSON depth
                    json_depth += line.count('{') - line.count('}')
                    if json_depth == 0:
                        break

            if self.debug:
                logger.debug(f"Raw response: {response}")

            return response.strip()

        except Exception as e:
            logger.error(f"Error reading response: {str(e)}")
            raise

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
            try:
                self.process.terminate()
                self.process.wait(timeout=1)  # Wait for process to terminate
            except subprocess.TimeoutExpired:
                self.process.kill()  # Force kill if not terminated
            finally:
                self.process = None