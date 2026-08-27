"""Quest runner: canonical transitions, checkpoints, progress, replay and resume."""

import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Any

from llm_quest_benchmark.constants import DEFAULT_QUEST_TIMEOUT
from llm_quest_benchmark.core.logging import LogManager, QuestLogger
from llm_quest_benchmark.core.progress import ProgressTracker, load_progress_manifest
from llm_quest_benchmark.core.provenance import engine_revision, quest_checksum
from llm_quest_benchmark.core.replay import ReplayError, replay_record, restore_progress_tracker, verify_environment
from llm_quest_benchmark.environments.qm import QMPlayerEnv as QuestEnvironment
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.harnesses.specs import build_treatment, get_spec
from llm_quest_benchmark.players.base import DecisionContext, QuestPlayer
from llm_quest_benchmark.schemas.config import HarnessConfig
from llm_quest_benchmark.schemas.records import (
    PROVENANCE_RUNTIME,
    REPLAY_PENDING,
    ProgressState,
    QuestAction,
    QuestSnapshot,
    QuestTransition,
    ResumeLineage,
    RunRecord,
)

# Configure logging
logging.getLogger("quest").setLevel(logging.WARNING)


def _agent_identity(agent: QuestPlayer, agent_config: Any | None) -> str:
    """Resolve the run identity before execution starts."""
    if agent_config is not None and getattr(agent_config, "agent_id", None):
        return str(agent_config.agent_id)
    return str(getattr(agent, "agent_id", None) or str(agent))


def _treatment_payload(agent: QuestPlayer, agent_config: Any | None) -> dict[str, Any]:
    """Build the canonical treatment recorded before the first transition."""
    if agent_config is not None:
        return agent_config.treatment().to_dict()

    # No config supplied: resolve the treatment from the player itself.
    harness = getattr(agent, "harness_name", "") or "human"
    spec = get_spec(harness)
    return build_treatment(
        harness=harness,
        model=str(getattr(agent, "model_name", "") or spec.name),
        temperature=float(getattr(agent, "temperature", 0.0) or 0.0),
        system_template=str(getattr(agent, "system_template", "none")),
        knob_values={
            "compaction_interval": getattr(agent, "_compaction_interval", None),
            "restore_limit": getattr(agent, "restore_limit", None),
            "adaptive_stall_steps": getattr(agent, "adaptive_stall_steps", None),
        },
    ).to_dict()


def run_quest_with_timeout(
    quest_path: str,
    agent: QuestPlayer,
    timeout: int = DEFAULT_QUEST_TIMEOUT,
    agent_config: HarnessConfig | Any | None = None,
    debug: bool = False,
    callbacks: list[Callable[[str, Any], None]] = None,
    max_steps: int | None = None,
    progress_manifest: str | None = None,
    resume_record: RunRecord | None = None,
    resume_path: str | None = None,
) -> QuestOutcome | None:
    """Run quest with timeout.

    max_steps: optional shared cap on agent steps per quest. None (default)
    preserves the prior unbounded-loop behavior; reaching the cap yields the
    resumable TRUNCATED outcome.
    """
    logger: QuestLogger | None = None
    executor: ThreadPoolExecutor | None = None
    runner: QuestRunner | None = None
    try:
        logger = QuestLogger(debug=debug, agent=_agent_identity(agent, agent_config))

        runner = QuestRunner(
            agent=agent,
            debug=debug,
            callbacks=callbacks or [],
            quest_logger=logger,
            agent_config=agent_config,
            max_steps=max_steps,
            progress_manifest=progress_manifest,
            resume_record=resume_record,
            resume_path=resume_path,
        )

        # Run quest with timeout
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(runner.run, quest_path)
        try:
            return future.result(timeout=max(timeout, 1))
        except FuturesTimeoutError:
            future.cancel()
            runner.request_stop("timeout")
            logger.logger.warning(f"Quest timed out after {timeout} seconds")

            # Persist timeout as authoritative outcome.
            logger.finish_run(
                QuestOutcome.TIMEOUT.name,
                0.0,
                terminal_snapshot=runner.current_snapshot(),
                progress=runner.progress_state(),
                diagnostics=runner.runtime_metrics(),
            )

            # Notify callbacks about the timeout
            if callbacks:
                for callback in callbacks:
                    try:
                        callback("timeout", {"message": f"Quest timed out after {timeout} seconds"})
                    except Exception as e:
                        logger.logger.error(f"Error in timeout callback: {e}")

            return QuestOutcome.TIMEOUT

    except Exception as e:
        if logger:
            logger.logger.error(f"Error running quest: {e}")
            logger.finish_run(
                QuestOutcome.ERROR.name,
                0.0,
                terminal_snapshot=runner.current_snapshot() if runner else None,
                progress=runner.progress_state() if runner else None,
                diagnostics=runner.runtime_metrics() if runner else None,
            )
        raise
    finally:
        if executor:
            executor.shutdown(wait=False, cancel_futures=True)


class QuestRunner:
    """Executes a quest as a sequence of canonical transitions.

    The runner owns the active-branch checkpoint stack, progress tracking,
    replay verification on resume, and transition construction.
    """

    def __init__(
        self,
        agent: QuestPlayer,
        debug: bool = False,
        callbacks: list[Callable[[str, Any], None]] = None,
        quest_logger: QuestLogger = None,
        agent_config=None,
        max_steps: int | None = None,
        progress_manifest: str | None = None,
        resume_record: RunRecord | None = None,
        resume_path: str | None = None,
    ):
        self.agent = agent
        self.debug = debug
        self.callbacks = callbacks or []
        self.step_count = 0
        self.env: QuestEnvironment | None = None
        self.agent_config = agent_config
        self.max_steps = max_steps
        self.resume_record = resume_record
        self.resume_path = resume_path
        self._stop_requested = threading.Event()
        self._stop_reason = ""

        self._transition_index = 0
        self._checkpoints: list[QuestSnapshot] = []
        self._snapshot: QuestSnapshot | None = None
        self._quest_checksum = ""
        self._restore_attempts = 0
        self._restores_accepted = 0
        self._restored_distance = 0
        self._progress_at_last_restore: float | None = None

        if resume_record is not None:
            # A resumed run keeps the manifest and reached milestones it recorded,
            # so progress stays monotonic across the interruption.
            self.progress = restore_progress_tracker(resume_record)
        else:
            self.progress = ProgressTracker(manifest=load_progress_manifest(progress_manifest))

        self.restore_limit = getattr(agent_config, "restore_limit", None) if agent_config else None

        # Set up central logging
        log_manager = LogManager()
        log_manager.setup(debug=debug)
        self.logger = log_manager.get_logger()

        # Use provided quest logger or create a new one
        self.quest_logger = quest_logger
        if self.quest_logger is None:
            self.quest_logger = QuestLogger(debug=self.debug, agent=_agent_identity(agent, agent_config))

        if debug:
            self.logger.debug(f"QuestRunner initialized with agent: {str(agent)}")

    # ---- runtime accessors -------------------------------------------------

    def request_stop(self, reason: str = "requested") -> None:
        """Signal runner loop to stop as soon as possible."""
        self._stop_reason = reason
        self._stop_requested.set()

    def current_snapshot(self) -> QuestSnapshot | None:
        """Latest canonical snapshot, usable as a final state on interruption."""
        return self._snapshot

    def progress_state(self) -> ProgressState:
        return self.progress.state()

    def runtime_metrics(self) -> dict[str, Any]:
        """Runner-owned metrics merged into the persisted run record."""
        progress_recovered = 0.0
        if self._progress_at_last_restore is not None:
            progress_recovered = max(0.0, self.progress.state().current - self._progress_at_last_restore)
        return {
            "restore": {
                "attempts": self._restore_attempts,
                "accepted": self._restores_accepted,
                "restored_distance": self._restored_distance,
                # Progress gained after the last accepted restore.
                "progress_recovered": round(progress_recovered, 4),
            },
            "forced_stop_reason": getattr(self.env, "forced_stop_reason", None) if self.env else None,
        }

    def _notify_callbacks(self, event: str, data: Any = None) -> None:
        """Notify all callbacks of an event"""
        for callback in self.callbacks:
            try:
                callback(event, data)
            except Exception as e:
                self.logger.error(f"Error in callback: {e}")

    # ---- setup -------------------------------------------------------------

    def initialize(self, quest: str) -> None:
        """Initialize environment and write complete run metadata."""
        try:
            if self.debug:
                self.logger.debug("Initializing environment for quest: %s", quest)
            language = str(self.resume_record.quest_language) if self.resume_record else "rus"
            self.env = QuestEnvironment(quest, language=language, debug=self.debug)

            lineage = None
            if self.resume_record is not None:
                lineage = ResumeLineage(
                    source_run_id=self.resume_record.run_id,
                    source_path=str(self.resume_path or ""),
                    resumed_from_index=len(self.resume_record.transitions),
                )

            self._quest_checksum = quest_checksum(self.env.quest_file)
            self.quest_logger.start_run(
                quest_file=self.env.quest_file,
                quest_name=Path(self.env.quest_file).stem,
                quest_checksum=self._quest_checksum,
                quest_language=self.env.language,
                engine_revision=engine_revision(),
                agent_id=_agent_identity(self.agent, self.agent_config),
                treatment=_treatment_payload(self.agent, self.agent_config),
                benchmark_id=getattr(self.agent_config, "benchmark_id", None) if self.agent_config else None,
                lineage=lineage,
            )
            self.logger.info(f"Running quest {quest} with agent: {str(self.agent)}")
        except Exception as e:
            self.logger.error("Failed to initialize environment: %s", str(e), exc_info=True)
            raise

    def _start_environment(self) -> QuestSnapshot:
        """Reset or resume the environment and seed checkpoints and progress."""
        if self.resume_record is None:
            snapshot = self.env.reset()
            self._checkpoints = [snapshot]
            self.progress.seed(snapshot)
            return snapshot

        record = self.resume_record
        verify_environment(record, self.env.quest_file)
        self._verify_resume_treatment(record)

        result = replay_record(self.env, record)
        self.logger.info("Verified %s recorded transitions before resuming", result.verified_transitions)

        self._checkpoints = result.checkpoints
        self._transition_index = max((t.index for t in record.transitions), default=0)
        self.step_count = sum(1 for t in record.transitions if t.action.is_choose)
        restore_metrics = (record.transcript_diagnostics or {}).get("restore") or {}
        self._restore_attempts = int(restore_metrics.get("attempts") or 0)
        self._restores_accepted = int(restore_metrics.get("accepted") or 0)
        self._restored_distance = int(restore_metrics.get("restored_distance") or 0)

        # Prior transitions stay part of the resumed run's record.
        self.quest_logger.adopt_transitions(record.transitions)
        self.agent.rebuild_from_transitions(record.transitions)
        return result.snapshot

    def _verify_resume_treatment(self, record: RunRecord) -> None:
        """Refuse to resume under a different treatment than was recorded."""
        current = _treatment_payload(self.agent, self.agent_config)
        recorded_signature = record.treatment_signature
        if recorded_signature and current.get("signature") != recorded_signature:
            raise ReplayError(
                "Treatment signature mismatch: recorded "
                f"{recorded_signature}, current {current.get('signature')}"
            )

    # ---- decision execution ------------------------------------------------

    def _decision_context(self) -> DecisionContext:
        remaining = None
        if self.restore_limit is not None:
            remaining = max(0, int(self.restore_limit) - self._restores_accepted)
        restore_allowed = bool(
            getattr(self.agent, "supports_restore", False)
            and len(self._checkpoints) > 1
            and (remaining is None or remaining > 0)
        )
        return DecisionContext(
            step=self.step_count + 1,
            checkpoints=list(self._checkpoints),
            restore_allowed=restore_allowed,
            restores_remaining=remaining,
            progress=self.progress.state(),
        )

    def _resolve_action(self, action: QuestAction, context: DecisionContext, snapshot: QuestSnapshot) -> QuestAction:
        """Validate the agent's action and clamp it into an executable one."""
        if action.is_restore:
            self._restore_attempts += 1
            index = int(action.checkpoint_index or 0)
            valid = (
                getattr(self.agent, "supports_restore", False)
                and context.restore_allowed
                and 1 <= index < len(self._checkpoints)
            )
            if valid:
                return QuestAction.restore(index)
            self.logger.warning(
                "Rejecting restore to checkpoint %s (allowed=%s, checkpoints=%s); choosing instead",
                index,
                context.restore_allowed,
                len(self._checkpoints),
            )
            response = self.agent.get_last_response()
            fallback = int(getattr(response, "action", 1) or 1)
            action = QuestAction(kind="choose", choice_index=fallback)

        index = int(action.choice_index or 1)
        num_choices = len(snapshot.choices)
        if index < 1 or index > num_choices:
            self.logger.error("RUNNER ERROR - Action %s out of range 1-%s; defaulting to 1", index, num_choices)
            index = 1
        checksum_hex = self._quest_checksum.removeprefix("sha256:")
        timestamp_base = 1_700_000_000_000 + (int(checksum_hex[:10], 16) % 100_000_000_000)
        return QuestAction.choose(
            choice_index=index,
            choice_id=str(snapshot.choices[index - 1]["id"]),
            performed_at_ms=timestamp_base + self._transition_index + 1,
        )

    def _execute(self, action: QuestAction) -> QuestSnapshot:
        if action.is_restore:
            # A restore truncates the active branch to the target checkpoint, so
            # each one strictly shortens the stack. Restores therefore cannot
            # loop: once the stack is one deep the runner offers no restore
            # until a choose extends the branch again.
            checkpoint_index = int(action.checkpoint_index)
            target = self._checkpoints[checkpoint_index - 1]
            after = self.env.restore(target)
            self._restored_distance += max(0, len(self._checkpoints) - checkpoint_index)
            self._checkpoints = self._checkpoints[:checkpoint_index]
            self._restores_accepted += 1
            self._progress_at_last_restore = self.progress.state().current
            return after

        after = self.env.step(int(action.choice_index), int(action.performed_at_ms))
        self._checkpoints.append(after)
        self.step_count += 1
        return after

    def _record_transition(
        self,
        before: QuestSnapshot,
        action: QuestAction,
        after: QuestSnapshot,
    ) -> QuestTransition:
        response = self.agent.get_last_response()
        usage: dict[str, Any] = {}
        if response is not None:
            usage = {
                "prompt_tokens": response.prompt_tokens or 0,
                "completion_tokens": response.completion_tokens or 0,
                "total_tokens": response.total_tokens or 0,
                "estimated_cost_usd": response.estimated_cost_usd,
            }

        self._transition_index += 1
        transition = QuestTransition(
            index=self._transition_index,
            before=before,
            action=action,
            after=after,
            response=response,
            usage=usage,
            progress=self.progress.observe(after),
            provenance=PROVENANCE_RUNTIME,
            replay_status=REPLAY_PENDING,
            reasoning_mode=getattr(self.agent, "reasoning_mode", None),
        )

        self.agent.on_transition(transition)
        self._notify_callbacks("game_state", transition)
        self.quest_logger.log_transition(transition)
        return transition

    def _finish(self, outcome: QuestOutcome, snapshot: QuestSnapshot | None) -> QuestOutcome:
        self.agent.on_game_end(snapshot)
        self.quest_logger.finish_run(
            outcome.name,
            reward=snapshot.reward if snapshot else 0.0,
            terminal_snapshot=snapshot,
            progress=self.progress.state(),
            diagnostics=self.runtime_metrics(),
        )
        return outcome

    # ---- main loop ---------------------------------------------------------

    def run(self, quest: str) -> QuestOutcome:
        """Run the quest until completion, truncation, or error."""
        if not self.agent:
            self.logger.error("No agent initialized!")
            return QuestOutcome.ERROR

        try:
            self.initialize(quest)
            self._notify_callbacks(
                "run_record",
                {
                    "run_id": self.quest_logger.current_run_id if self.quest_logger else None,
                    "quest": quest,
                },
            )
            self.agent.reset()
            self.agent.on_game_start()
            self._notify_callbacks("title")
            self._notify_callbacks("progress", {"step": 0, "message": "Starting quest..."})

            snapshot = self._start_environment()
            self._snapshot = snapshot

            while True:
                if self._stop_requested.is_set():
                    self.logger.warning("Quest runner stop requested: %s", self._stop_reason or "unknown")
                    return QuestOutcome.TIMEOUT

                if snapshot.done:
                    # Terminal state is the after-snapshot of the last executed
                    # transition, never a synthetic decision row.
                    outcome = QuestOutcome.SUCCESS if snapshot.game_state == "win" else QuestOutcome.FAILURE
                    return self._finish(outcome, snapshot)

                if not snapshot.choices:
                    self.logger.warning("No choices available at location %s", snapshot.location_id)
                    return self._finish(QuestOutcome.FAILURE, snapshot)

                if self.max_steps is not None and self.step_count >= self.max_steps:
                    self.logger.warning("Quest reached max steps (%s); recording TRUNCATED", self.max_steps)
                    return self._finish(QuestOutcome.TRUNCATED, snapshot)

                self._notify_callbacks(
                    "progress", {"step": self.step_count + 1, "message": f"Processing step {self.step_count + 1}..."}
                )

                context = self._decision_context()
                proposed = self.agent.get_quest_action(snapshot.agent_observation(), snapshot.choices, context)
                action = self._resolve_action(proposed, context, snapshot)

                if self.debug:
                    self.logger.debug("Agent action: %s", action.to_dict())

                if self._stop_requested.is_set():
                    self.logger.info("Quest runner stopped before step after %s", self._stop_reason or "request")
                    return QuestOutcome.TIMEOUT

                try:
                    after = self._execute(action)
                except Exception as e:
                    if self._stop_requested.is_set():
                        self.logger.info("Quest runner stopped during step after %s", self._stop_reason or "request")
                        return QuestOutcome.TIMEOUT
                    self.logger.error("Error during step: %s", str(e), exc_info=True)
                    raise

                self._record_transition(snapshot, action, after)
                snapshot = after
                self._snapshot = snapshot

        except ReplayError as e:
            self.logger.error("Resume verification failed: %s", str(e))
            self._notify_callbacks("error", str(e))
            self.quest_logger.finish_run(
                QuestOutcome.ERROR.name,
                0.0,
                terminal_snapshot=self._snapshot,
                progress=self.progress.state(),
                diagnostics=self.runtime_metrics(),
            )
            raise
        except Exception as e:
            if self._stop_requested.is_set():
                self.logger.info("Quest runner stopped after %s", self._stop_reason or "request")
                return QuestOutcome.TIMEOUT
            self.logger.error("Error running quest: %s", str(e), exc_info=True)
            self._notify_callbacks("error", str(e))
            self.agent.on_game_end(self._snapshot)
            self.quest_logger.finish_run(
                QuestOutcome.ERROR.name,
                0.0,
                terminal_snapshot=self._snapshot,
                progress=self.progress.state(),
                diagnostics=self.runtime_metrics(),
            )
            return QuestOutcome.ERROR
        finally:
            self._notify_callbacks("close")
