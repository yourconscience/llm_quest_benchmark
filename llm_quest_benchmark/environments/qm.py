"""QM environment for Space Rangers quests"""

import logging
from collections import Counter

from llm_quest_benchmark.executors.ts_bridge.bridge import QMBridge
from llm_quest_benchmark.schemas.records import QuestSnapshot

LOOP_GUARD_MIN_STATES = 30
LOOP_GUARD_WINDOW = 10
LOOP_GUARD_REPEATS = 5
FORCED_STOP_TEXT = "[Forced stop: repetitive state loop detected before terminal quest outcome]"


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
    """Environment for playing QM files using the TypeScript bridge.

    The environment owns canonical snapshots: every reset, step, and restore
    returns a ``QuestSnapshot`` carrying the full engine saving and a
    deterministic digest over the canonical state fields.
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
        self.forced_stop_reason: str | None = None

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
            self._snapshot: QuestSnapshot | None = None
        except Exception as e:
            self.logger.error(f"Failed to initialize QMPlayerEnv: {e}")
            raise RuntimeError(f"Failed to initialize QMPlayerEnv: {e}")

    @property
    def snapshot(self) -> QuestSnapshot | None:
        """Current canonical snapshot, or None before reset."""
        return self._snapshot

    def _require_snapshot(self) -> QuestSnapshot:
        if self._snapshot is None:
            raise RuntimeError("Environment not initialized - call reset() first")
        return self._snapshot

    def reset(self) -> QuestSnapshot:
        """Start the quest and return the initial snapshot."""
        try:
            self.forced_stop_reason = None
            initial_bridge_state = self.bridge.start_game()
            if not initial_bridge_state:
                raise RuntimeError("Failed to get initial state from bridge")

            self._snapshot = initial_bridge_state.to_snapshot()
            if not self._snapshot.choices and not self._snapshot.done:
                raise RuntimeError("No valid choices in initial state")
            return self._snapshot
        except Exception as e:
            self.logger.error(f"Failed to reset environment: {e}")
            self.bridge.close()  # Clean up on error
            raise RuntimeError(f"Failed to reset environment: {e}")

    def _detect_state_loop(self) -> bool:
        """Detect a repeating non-terminal state loop across recent engine states.

        This is a general guard for quests (like Prison.qm) whose daily-routine
        branches can cycle forever without reaching a terminal outcome.
        """
        history = self.bridge.state_history
        if len(history) <= LOOP_GUARD_MIN_STATES:
            return False

        fragments = [state.text[:20].strip() for state in history[-LOOP_GUARD_WINDOW:] if state.text]
        counts = Counter(fragments)
        return any(count >= LOOP_GUARD_REPEATS for count in counts.values())

    def _forced_stop_snapshot(self) -> QuestSnapshot:
        """Terminal snapshot for the loop guard; never a quest success."""
        current = self._require_snapshot()
        return QuestSnapshot(
            location_id=current.location_id,
            observation=f"{current.observation}\n\n{FORCED_STOP_TEXT}",
            choices=[],
            params_state=list(current.params_state),
            reward=current.reward,
            done=True,
            game_state="fail",
            saving=current.saving,
        )

    def step(self, choice_index: int, performed_at_ms: int) -> QuestSnapshot:
        """Execute a one-based choice and return the resulting snapshot.

        ``performed_at_ms`` is recorded with the transition and handed to the
        engine, so replaying the same timestamp reproduces dynamic branches.
        """
        self._require_snapshot()

        if self._detect_state_loop():
            self.logger.warning("Detected potential infinite loop after %s states", len(self.bridge.state_history))
            self.forced_stop_reason = "infinite_loop_detected"
            self._snapshot = self._forced_stop_snapshot()
            return self._snapshot

        try:
            new_bridge_state = self.bridge.step(choice_index, performed_at_ms)
            if not new_bridge_state:
                raise RuntimeError("Failed to get new state from bridge")

            self._snapshot = new_bridge_state.to_snapshot()

            if self._snapshot.done:
                self.logger.info(
                    f"Game ended: game_state={self._snapshot.game_state}, "
                    f"location={self._snapshot.location_id}, success={self._snapshot.game_state == 'win'}"
                )
            return self._snapshot
        except Exception as e:
            self.logger.error(f"Failed to take step: {e}")
            self.bridge.close()  # Clean up on error
            raise RuntimeError(f"Failed to take step: {e}")

    def restore(self, snapshot: QuestSnapshot) -> QuestSnapshot:
        """Restore the engine to an exact recorded snapshot.

        The restored snapshot must reproduce the recorded digest; a mismatch
        means the engine or the record diverged and the run cannot continue.
        """
        if not snapshot.is_resumable:
            raise ValueError("Cannot restore a snapshot without a full engine saving")

        try:
            restored_state = self.bridge.load_saving(snapshot.saving)
        except Exception as e:
            self.logger.error(f"Failed to restore snapshot: {e}")
            raise RuntimeError(f"Failed to restore snapshot: {e}")

        restored = restored_state.to_snapshot()
        if restored.digest != snapshot.digest:
            raise RuntimeError(
                f"Restored state digest does not match the recorded snapshot ({restored.digest} != {snapshot.digest})"
            )
        self.forced_stop_reason = None
        self._snapshot = restored
        return restored

    def close(self):
        """Clean up resources"""
        if hasattr(self, "bridge"):
            self.bridge.close()
