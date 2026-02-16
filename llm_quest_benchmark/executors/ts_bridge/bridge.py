"""TypeScript bridge for QM file parsing and execution"""
import logging
import json
import os
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Optional, Any

from llm_quest_benchmark.schemas.bridge import QMBridgeState
from llm_quest_benchmark.utils.text_processor import clean_qm_text

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
        self._validate_bridge_dependencies()

    def _required_bridge_sources(self) -> List[Path]:
        """Return required TypeScript source files for bridge imports."""
        repo_root = self.parser_script.parents[3]
        return [
            repo_root / "space-rangers-quest/src/lib/qmreader.ts",
            repo_root / "space-rangers-quest/src/lib/qmplayer/index.ts",
        ]

    def _validate_bridge_dependencies(self) -> None:
        """Validate that the TypeScript quest engine sources exist."""
        missing_files = [path for path in self._required_bridge_sources() if not path.exists()]
        if missing_files:
            missing_preview = ", ".join(str(path) for path in missing_files[:2])
            raise RuntimeError(
                "TypeScript bridge dependencies are missing "
                f"({missing_preview}). Run: git submodule update --init --recursive"
            )

    @staticmethod
    def _submodule_help() -> str:
        return "Run: git submodule update --init --recursive"

    def _build_node_env(self) -> Dict[str, str]:
        """Build subprocess environment with Node compatibility defaults."""
        env = os.environ.copy()
        node_options = env.get("NODE_OPTIONS", "")
        legacy_flag = "--openssl-legacy-provider"
        if legacy_flag not in node_options:
            env["NODE_OPTIONS"] = f"{node_options} {legacy_flag}".strip()
        return env

    def _read_stderr_snapshot(self, max_lines: int = 8, timeout: float = 0.2) -> str:
        """Read a small non-blocking stderr snapshot for diagnostics."""
        if not self.process or not self.process.stderr:
            return ""

        import select

        lines: List[str] = []
        for _ in range(max_lines):
            ready, _, _ = select.select([self.process.stderr], [], [], timeout)
            if not ready:
                break
            line = self.process.stderr.readline()
            if not line:
                break
            lines.append(line.strip())
        return "\n".join(line for line in lines if line)

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

    @staticmethod
    def _is_probably_json(raw: str) -> bool:
        text = (raw or "").strip()
        return text.startswith("{") or text.startswith("[")

    def _parse_response_json(self, raw: str) -> Optional[Dict[str, Any]]:
        """Parse one bridge line into JSON dict, returning None on non-JSON/noise lines."""
        text = (raw or "").strip()
        if not text or not self._is_probably_json(text):
            return None

        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            pass

        try:
            from json_repair import repair_json
            repaired = repair_json(text)
            parsed = json.loads(repaired)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None

    def _read_response_json(self, timeout: int = 10, require_state: bool = True) -> Dict[str, Any]:
        """Read bridge stdout until we get a valid JSON response packet."""
        if not self.process:
            raise RuntimeError("Game process not started")

        import select
        import time

        deadline = time.monotonic() + timeout
        skipped_lines = 0
        last_candidate: Optional[Dict[str, Any]] = None

        while time.monotonic() < deadline:
            remaining = max(0.05, deadline - time.monotonic())
            if not select.select([self.process.stdout], [], [], remaining)[0]:
                continue

            raw = self.process.stdout.readline()
            if self.debug:
                logger.debug(f"Raw response line: {raw[:500]}...")
            if not raw:
                continue

            parsed = self._parse_response_json(raw)
            if parsed is None:
                skipped_lines += 1
                continue

            last_candidate = parsed

            if "error" in parsed:
                raise RuntimeError(f"TypeScript bridge error: {parsed.get('error')}")

            if require_state and ("state" not in parsed or "saving" not in parsed):
                skipped_lines += 1
                continue

            if skipped_lines > 0 and self.debug:
                logger.debug("Skipped %s non-protocol bridge lines before valid JSON packet", skipped_lines)
            return parsed

        stderr_snapshot = self._read_stderr_snapshot()
        details = f"Bridge stderr:\n{stderr_snapshot}\n" if stderr_snapshot else ""
        if last_candidate is not None:
            keys = ", ".join(sorted(last_candidate.keys()))
            raise TimeoutError(
                f"Timed out waiting for valid bridge state packet. Last JSON keys: [{keys}].\n{details}"
            )
        raise TimeoutError(f"Timeout waiting for JSON response from TypeScript bridge.\n{details}")

    def parse_quest_locations(self) -> Dict[str, Any]:
        """Parse quest file and return metadata including locations and start location"""
        cmd = ["node", "-r", "ts-node/register", str(self.parser_script), str(self.quest_file), "--parse"]

        if self.debug:
            logger.debug(f"Running parser command: {' '.join(cmd)}")

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                env=self._build_node_env(),
            )
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
            raise RuntimeError(
                f"Failed to parse quest file: {e.stderr}\n{self._submodule_help()}"
            )
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
                bufsize=1,  # Line buffered
                env=self._build_node_env(),
            )

            response = self._read_response_json(timeout=10, require_state=True)
            state = response['state']
            choices = [
                {'id': str(c['jumpId']), 'text': clean_qm_text(c['text'])}
                for c in state['choices'] if c['active']
            ]
            initial_state = QMBridgeState(
                location_id=str(response['saving']['locationId']),
                text=clean_qm_text(state['text']),
                choices=choices,
                reward=0.0,  # Initial state has no reward
                game_ended=state['gameState'] != 'running'
            )

            if not initial_state.choices and not initial_state.game_ended:
                raise RuntimeError("No valid choices in initial state")

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

            response_data = self._read_response_json(timeout=10, require_state=True)

            state = response_data['state']
            current_state = QMBridgeState(
                location_id=str(response_data['saving']['locationId']),
                text=clean_qm_text(state['text']),
                choices=[{'id': str(c['jumpId']), 'text': clean_qm_text(c['text'])} for c in state['choices'] if c['active']],
                reward=0.0,  # Get reward from game state if available
                game_ended=state['gameState'] != 'running'
            )

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
                current_state = self.state_history[-1] if self.state_history else self.get_current_state()
                logger.debug(f"Step with choice_num: {choice_num}, jump_id: {jump_id}")
                choices_debug = []
                for i, c in enumerate(current_state.choices):
                    choices_debug.append(f"{i+1}: {c['text']}")
                logger.debug(f"Current choices: {choices_debug}")
                logger.debug(f"Current choices raw: {current_state.choices}")

            # Send jump ID to process
            self.process.stdin.write(f"{jump_id}\n")
            self.process.stdin.flush()

            response_data = self._read_response_json(timeout=10, require_state=True)
            state = response_data['state']

            location_id = str(response_data['saving'].get('locationId', 0))
            choices = []
            if 'choices' in state:
                choices = [
                    {'id': str(c.get('jumpId', 0)), 'text': clean_qm_text(c.get('text', ''))}
                    for c in state['choices']
                    if c.get('active', True)
                ]

            new_state = QMBridgeState(
                location_id=location_id,
                text=clean_qm_text(state.get('text', 'Game text unavailable.')),
                choices=choices,
                reward=float(state.get('reward', 0.0)),
                game_ended=state.get('gameState', 'complete') != 'running'
            )

            if not new_state.choices and not new_state.game_ended:
                raise RuntimeError("No valid choices in running state")

            self.state_history.append(new_state)
            return new_state

        except Exception as e:
            logger.error(f"Failed to take step: {str(e)}")
            self.close()  # Clean up on error
            raise RuntimeError(f"Failed to take step: {str(e)}")

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
