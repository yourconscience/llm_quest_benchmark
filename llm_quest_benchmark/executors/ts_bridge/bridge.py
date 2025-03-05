"""TypeScript bridge for QM file parsing and execution"""
import json
import logging
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

from llm_quest_benchmark.schemas.bridge import QMBridgeState
from llm_quest_benchmark.utils.text_processor import clean_qm_text, detect_quest_outcome

logger = logging.getLogger(__name__)

# Global flags to control log verbosity across all bridge instances
_VERBOSE_JSON_LOGGING = False  # Set to True for debugging
_LOG_MISSING_STATE_WARNING = True  # Will be set to False after first global warning
_LOG_JSON_ERROR_WARNING = True  # Will be set to False after first JSON error warning
_QUEST_JSON_FAILURES = set()  # Track quests with JSON parsing issues to prevent repeated warnings


class QMBridge:
    """Bridge to TypeScript QM parser and executor"""

    def __init__(self, quest_file: str, debug: bool = False):
        """Initialize bridge with quest file path"""
        self.quest_file = Path(quest_file).resolve()
        self.debug = debug
        self.process = None
        self.parser_script = Path(__file__).parent / "consoleplayer.ts"
        self.state_history: List[QMBridgeState] = []

        # Validate quest file exists
        if not self.quest_file.exists():
            raise FileNotFoundError(f"Quest file not found: {quest_file}")

        # Validate parser script exists
        if not self.parser_script.exists():
            raise FileNotFoundError(f"Parser script not found: {self.parser_script}")

    def _read_response(self, timeout: int = 10) -> str:
        """Read response from process with timeout"""
        if not self.process:
            raise RuntimeError("Game process not started")

        import select
        if select.select([self.process.stdout], [], [], timeout)[0]:
            response = self.process.stdout.readline()
            if self.debug:
                logger.debug(f"Raw response: {response[:500]}...")

            # Check for empty response, which can happen with some quests
            if not response or response.strip() == '':
                logger.warning("Empty response received from TypeScript bridge")
                # Try one more time as sometimes the first line is empty
                if select.select([self.process.stdout], [], [], timeout)[0]:
                    response = self.process.stdout.readline()
                    if self.debug:
                        logger.debug(f"Second attempt raw response: {response[:500]}...")
                else:
                    raise TimeoutError("Timeout waiting for response after empty line")

            return response
        else:
            raise TimeoutError("Timeout waiting for response from TypeScript bridge")

    def parse_quest_locations(self) -> Dict[str, Any]:
        """Parse quest file and return metadata including locations and start location"""
        cmd = [
            "node", "-r", "ts-node/register",
            str(self.parser_script),
            str(self.quest_file), "--parse"
        ]

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
                    output = output[output.find('{'):output.rfind('}') + 1]
                repaired_json = repair_json(output)
                qm_data = json.loads(repaired_json)
            except ImportError:
                # Fallback to direct JSON parsing if json-repair not available
                qm_data = json.loads(proc.stdout)

            metadata = qm_data.get('metadata', {})
            total_locations = len(metadata.get('locations', []))
            start_location = metadata.get('startLocationId', 0)

            if self.debug:
                logger.debug(
                    f"Parsed metadata: start location {start_location}, total locations: {total_locations}"
                )

            return {
                'start_location_id': start_location,
                'locations': metadata.get('locations', []),
                'total_locations': total_locations if total_locations > 0 else
                                   20  # Default fallback for progress bar
            }

        except subprocess.CalledProcessError as e:
            logger.error(f"Node parser error:\n{e.stderr}")
            raise RuntimeError(f"Failed to parse quest file: {e.stderr}")
        except Exception as e:
            logger.error(f"Failed to parse QM data: {str(e)}")
            raise RuntimeError(f"Failed to parse quest file: {str(e)}")

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
            try:
                try:
                    # First attempt direct parsing
                    response = json.loads(initial_raw)
                except json.JSONDecodeError:
                    # If that fails, try more robust methods
                    global _LOG_JSON_ERROR_WARNING, _QUEST_JSON_FAILURES

                    quest_name = Path(self.quest_file).name

                    # Only log if we haven't already seen a failure for this quest
                    if quest_name not in _QUEST_JSON_FAILURES:
                        _QUEST_JSON_FAILURES.add(quest_name)

                        if _LOG_JSON_ERROR_WARNING:
                            logger.warning(
                                f"JSON parsing failed for {quest_name}, attempting repair. JSON errors for other quests will not be logged."
                            )
                            # Disable future warnings except for debug mode
                            _LOG_JSON_ERROR_WARNING = False
                        elif self.debug:
                            logger.warning(
                                f"JSON parsing failed for {quest_name}, attempting repair (debug mode)"
                            )

                    try:
                        # Try with json-repair library if available
                        from json_repair import repair_json
                        repaired_json = repair_json(initial_raw)
                        response = json.loads(repaired_json)
                        logger.debug("JSON repaired successfully")
                    except ImportError:
                        # Manual JSON repair if json-repair not available
                        logger.debug("json-repair not available, attempting manual repair")
                        clean_response = initial_raw.strip()
                        if '{' in clean_response:
                            clean_response = clean_response[clean_response.
                                                            find('{'):clean_response.rfind('}') + 1]
                        response = json.loads(clean_response)

                if 'state' not in response:
                    raise RuntimeError("Invalid response format: missing 'state' field")

                state = response['state']
                initial_state = QMBridgeState(
                    location_id=str(response['saving']['locationId']),
                    text=clean_qm_text(state['text']),
                    choices=[{
                        'id': str(c['jumpId']),
                        'text': clean_qm_text(c['text'])
                    } for c in state['choices'] if c['active']],
                    reward=0.0,  # Initial state has no reward
                    game_ended=state['gameState'] != 'running')

                if not initial_state.choices:
                    raise RuntimeError("No valid choices in initial state")

                self.state_history.append(initial_state)
                return initial_state
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                logger.error(f"Initial response that failed parsing: {initial_raw[:300]}")
                raise RuntimeError(f"Invalid JSON response from TypeScript bridge: {e}")

            # This line should never be reached due to the return inside the try block
            # but just in case, let's raise an exception
            raise RuntimeError("Unexpected execution path in start_game method")

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
            try:
                response_data = json.loads(response)
            except json.JSONDecodeError as e:
                raise RuntimeError(f"Invalid JSON response from TypeScript bridge: {e}")

            if 'state' not in response_data:
                raise RuntimeError("Invalid response format: missing 'state' field")

            state = response_data['state']
            current_state = QMBridgeState(
                location_id=str(response_data['saving']['locationId']),
                text=clean_qm_text(state['text']),
                choices=[{
                    'id': str(c['jumpId']),
                    'text': clean_qm_text(c['text'])
                } for c in state['choices'] if c['active']],
                reward=0.0,  # Get reward from game state if available
                game_ended=state['gameState'] != 'running')

            if not current_state.choices and not current_state.game_ended:
                raise RuntimeError("No valid choices in current state")

            return current_state

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
            raise ValueError(f"Invalid choice {choice_num}. Valid choices: {valid_choices}\n"
                             f"Current state: {json.dumps(current_state.__dict__, indent=2)}")

        return current_state.choices[choice_num - 1]['id']

    def step(self, choice_num: int) -> QMBridgeState:
        """Take a step in the game with choice number (1-based)"""
        if not self.process:
            raise RuntimeError("Game not started")

        try:
            # Validate and map choice
            jump_id = self.validate_choice(choice_num)

            if self.debug:
                current_state = self.state_history[
                    -1] if self.state_history else self.get_current_state()
                logger.debug(f"Step with choice_num: {choice_num}, jump_id: {jump_id}")
                choices_debug = []
                for i, c in enumerate(current_state.choices):
                    choices_debug.append(f"{i+1}: {c['text']}")
                logger.debug(f"Current choices: {choices_debug}")
                logger.debug(f"Current choices raw: {current_state.choices}")

            # Send jump ID to process
            self.process.stdin.write(f"{jump_id}\n")
            self.process.stdin.flush()

            # Read response
            response = self._read_response()
            if not response:
                logger.warning(
                    "No response received from TypeScript bridge, trying to get current state")
                try:
                    # Try to get current state directly as a fallback
                    return self.get_current_state()
                except Exception as fallback_error:
                    logger.error(f"Failed to get current state as fallback: {fallback_error}")
                    # Now raise the original error
                    raise RuntimeError("No response received from TypeScript bridge")

            # Parse response and extract state
            try:
                try:
                    # First attempt direct parsing
                    response_data = json.loads(response)
                except json.JSONDecodeError:
                    # If that fails, try more robust methods
                    global _VERBOSE_JSON_LOGGING, _LOG_JSON_ERROR_WARNING, _QUEST_JSON_FAILURES

                    quest_name = Path(self.quest_file).name

                    # Only log if we haven't already seen a failure for this quest
                    if quest_name not in _QUEST_JSON_FAILURES:
                        _QUEST_JSON_FAILURES.add(quest_name)

                        if _LOG_JSON_ERROR_WARNING:
                            logger.warning(
                                f"JSON parsing failed for {quest_name}, attempting repair. JSON errors for other quests will not be logged."
                            )
                            # Disable future warnings except for debug mode
                            _LOG_JSON_ERROR_WARNING = False
                        elif self.debug or _VERBOSE_JSON_LOGGING:
                            logger.warning(
                                f"JSON parsing failed for response in {quest_name}, attempting repair (debug mode)"
                            )

                    try:
                        # Try with json-repair library if available
                        from json_repair import repair_json
                        repaired_json = repair_json(response)
                        response_data = json.loads(repaired_json)
                        if self.debug:
                            logger.debug("JSON repaired successfully")
                    except ImportError:
                        # Manual JSON repair if json-repair not available
                        if self.debug:
                            logger.debug("json-repair not available, attempting manual repair")
                        clean_response = response.strip()
                        if '{' in clean_response:
                            clean_response = clean_response[clean_response.
                                                            find('{'):clean_response.rfind('}') + 1]
                        response_data = json.loads(clean_response)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                logger.error(f"Response that failed parsing: {response[:300]}")
                raise RuntimeError(f"Invalid JSON response from TypeScript bridge: {e}")

            # Handle the case where the game might have ended abruptly or the response is malformed
            if 'state' not in response_data:
                # Use global flag to only log this warning once across all quests
                global _LOG_MISSING_STATE_WARNING

                # Only log warning in specific circumstances to avoid spam
                if self.debug:
                    logger.warning(
                        "Response missing 'state' field, checking if game ended or using fallback")
                elif _LOG_MISSING_STATE_WARNING:
                    quest_name = Path(self.quest_file).name
                    logger.warning(
                        f"Response missing 'state' field in {quest_name}, using fallback. This is normal for completed quests and will not be logged again."
                    )
                    # Disable the warning for all future bridge instances
                    _LOG_MISSING_STATE_WARNING = False

                # Create a fallback state regardless of what data we have
                if self.debug:
                    logger.info("Creating artificial state to recover from error")
                last_state = self.state_history[-1] if self.state_history else None

                # Use the last known state's text or a generic message
                text = "Game ended unexpectedly."
                location_id = "0"

                # Make sure response_data is a dictionary
                if not isinstance(response_data, dict):
                    # Only log in debug mode to avoid spam
                    if self.debug:
                        logger.warning(
                            f"Response data is {type(response_data)}, creating empty dict")
                    response_data = {}

                # Extract location from saving data if available
                if 'saving' in response_data and isinstance(
                        response_data['saving'], dict) and 'locationId' in response_data['saving']:
                    location_id = str(response_data['saving'].get('locationId', 0))

                if last_state:
                    text = last_state.text + "\n\n[Game progressed to next state]"
                    if not location_id or location_id == "0":
                        location_id = last_state.location_id

                # Check for keywords in the text that might indicate success or failure
                reward = 0.0
                if last_state and last_state.text:
                    # Use our centralized quest outcome detection utility
                    success, detected_reward, reason = detect_quest_outcome(last_state.text)

                    if success:
                        reward = 1.0  # Use standard 1.0 for positive outcome in bridge
                        logger.info(f"Detected success in text ({reason})")
                        if detected_reward > 0:
                            logger.info(f"Found reward value: {detected_reward}")
                    elif reason != "no_indicators":
                        logger.info(f"Detected failure in text ({reason})")

                # Create a synthetic state to allow graceful continuation
                response_data['state'] = {
                    'text': text,
                    'choices': [],
                    'gameState': 'complete',
                    'reward': reward
                }

                logger.debug(f"Created synthetic state: {response_data['state']}")

            state = response_data['state']
            # Additional safety for missing or malformed fields
            try:
                # Get location ID safely
                location_id = "0"
                if 'saving' in response_data and 'locationId' in response_data['saving']:
                    location_id = str(response_data['saving']['locationId'])

                # Get choices safely
                choices = []
                if 'choices' in state:
                    choices = [{
                        'id': str(c.get('jumpId', 0)),
                        'text': clean_qm_text(c.get('text', ''))
                    } for c in state['choices'] if c.get('active', True)]

                # Create state object
                new_state = QMBridgeState(location_id=location_id,
                                          text=clean_qm_text(
                                              state.get('text', 'Game text unavailable.')),
                                          choices=choices,
                                          reward=float(state.get('reward', 0.0)),
                                          game_ended=state.get('gameState', 'complete')
                                          != 'running')

                # Log warning if we had to create a synthetic state or parts of it
                if not choices and not new_state.game_ended:
                    logger.warning(
                        "Created QMBridgeState with no choices but game not marked as ended")
            except Exception as e:
                logger.error(f"Error creating QMBridgeState: {e}")
                # Create a minimal valid state as a fallback
                new_state = QMBridgeState(location_id="0",
                                          text="An error occurred while processing the game state.",
                                          choices=[],
                                          reward=0.0,
                                          game_ended=True)

            # If there are no choices and the game isn't marked as ended,
            # Force it to end to avoid getting stuck
            if not new_state.choices and not new_state.game_ended:
                logger.warning("No valid choices but game not ended - forcing game end")
                new_state = QMBridgeState(location_id=new_state.location_id,
                                          text=new_state.text +
                                          "\n\n[Game ended due to no available choices]",
                                          choices=[],
                                          reward=new_state.reward,
                                          game_ended=True)

            self.state_history.append(new_state)
            return new_state

        except Exception as e:
            logger.error(f"Failed to take step: {str(e)}")
            self.close()  # Clean up on error
            raise RuntimeError(f"Failed to take step: {str(e)}")

    def get_debug_state(self) -> str:
        """Get formatted debug state"""
        current_state = self.state_history[-1] if self.state_history else self.get_current_state()
        return (f"Location: {current_state.location_id}\n"
                f"Game ended: {current_state.game_ended}\n"
                f"Reward: {current_state.reward}\n"
                f"Choices:\n" + "\n".join(f"{i+1}. {c['text']} (id: {c['id']})"
                                          for i, c in enumerate(current_state.choices)))

    def close(self):
        """Clean up resources"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            finally:
                self.process = None
                self.state_history.clear()
