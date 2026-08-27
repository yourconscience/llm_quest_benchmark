"""Deterministic replay and resume verification for schema-v2 run records.

Replay re-executes recorded choose timestamps and restore actions against the
real engine and compares every resulting snapshot digest. Resume runs this
verification before any new model inference.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from llm_quest_benchmark.core.progress import ProgressTracker, load_progress_manifest
from llm_quest_benchmark.core.provenance import engine_revision, quest_checksum
from llm_quest_benchmark.environments.qm import QMPlayerEnv
from llm_quest_benchmark.schemas.records import QuestSnapshot, RunRecord


class ReplayError(RuntimeError):
    """Raised when a record cannot be reproduced against the live engine."""


@dataclass
class ReplayResult:
    """Outcome of replaying a full record."""

    snapshot: QuestSnapshot
    checkpoints: list[QuestSnapshot] = field(default_factory=list)
    verified_transitions: int = 0


def verify_environment(record: RunRecord, quest_file: str) -> None:
    """Verify quest identity and engine revision before replaying."""
    actual_checksum = quest_checksum(quest_file)
    if record.quest_checksum and record.quest_checksum != actual_checksum:
        raise ReplayError(
            f"Quest checksum mismatch for {quest_file}: recorded {record.quest_checksum}, found {actual_checksum}"
        )

    actual_engine = engine_revision()
    if record.engine_revision and record.engine_revision != actual_engine:
        raise ReplayError(f"Engine revision mismatch: recorded {record.engine_revision}, found {actual_engine}")


def _seed_from_record(env: QMPlayerEnv, record: RunRecord) -> QuestSnapshot:
    """Put the engine into the exact state the record starts from.

    The engine seeds its PRNG per process (``initGame`` takes a random seed), so
    a fresh ``reset`` produces a different ``aleaSeed``/``aleaState`` than the
    recorded run even though the quest text is identical. Replay therefore boots
    the process and then loads the recorded opening saving, which is the
    authoritative engine state: ``restore`` re-derives the observation, choices,
    and parameter state from it and fails if they do not reproduce the recorded
    digest.
    """
    snapshot = env.reset()
    if not record.transitions:
        return snapshot

    first_transition = record.transitions[0]
    first = first_transition.before
    if not first.is_resumable:
        raise ReplayError(
            f"Transition {first_transition.index} is not replayable: its before-state carries no "
            f"engine saving (provenance={first_transition.provenance})"
        )
    try:
        return env.restore(first)
    except Exception as exc:  # engine refused the saving, or the state diverged
        raise ReplayError(f"Recorded opening state could not be reproduced: {exc}") from exc


def replay_record(env: QMPlayerEnv, record: RunRecord) -> ReplayResult:
    """Replay every recorded transition, verifying each resulting digest.

    The environment must not have been reset yet; this function drives it from
    the recorded opening state through the whole recorded trajectory.
    """
    snapshot = _seed_from_record(env, record)
    checkpoints: list[QuestSnapshot] = [snapshot]

    for transition in record.transitions:
        if not transition.is_replayable:
            raise ReplayError(
                f"Transition {transition.index} is not replayable "
                f"(provenance={transition.provenance}, replay_status={transition.replay_status})"
            )
        if transition.before.digest != snapshot.digest:
            raise ReplayError(
                f"Transition {transition.index} before-state diverged ({snapshot.digest} != {transition.before.digest})"
            )

        action = transition.action
        if action.is_choose:
            index = int(action.choice_index or 0)
            if not (1 <= index <= len(snapshot.choices)):
                raise ReplayError(f"Transition {transition.index} choice index {index} is out of range")
            recorded_id = str(action.choice_id)
            live_id = str(snapshot.choices[index - 1]["id"])
            if recorded_id != live_id:
                raise ReplayError(
                    f"Transition {transition.index} choice id diverged (recorded {recorded_id}, found {live_id})"
                )
            snapshot = env.step(index, int(action.performed_at_ms))
            checkpoints.append(snapshot)
        else:
            checkpoint_index = int(action.checkpoint_index or 0)
            if not (1 <= checkpoint_index <= len(checkpoints)):
                raise ReplayError(
                    f"Transition {transition.index} restores checkpoint {checkpoint_index}, "
                    f"but only {len(checkpoints)} are on the active branch"
                )
            snapshot = env.restore(checkpoints[checkpoint_index - 1])
            checkpoints = checkpoints[:checkpoint_index]

        if snapshot.digest != transition.after.digest:
            raise ReplayError(
                f"Transition {transition.index} after-state diverged ({snapshot.digest} != {transition.after.digest})"
            )

    return ReplayResult(snapshot=snapshot, checkpoints=checkpoints, verified_transitions=len(record.transitions))


def restore_progress_tracker(record: RunRecord) -> ProgressTracker:
    """Rebuild the progress tracker, including its manifest, from a record.

    A manifest that no longer hashes to what the run was scored under would make
    the resumed progress incomparable with the recorded part, so it is rejected
    rather than silently re-scored.
    """
    manifest_path = record.progress.manifest
    manifest = None
    if manifest_path and Path(manifest_path).exists():
        manifest = load_progress_manifest(manifest_path)

    recorded_hash = record.progress.manifest_hash
    if manifest is not None and recorded_hash and manifest.hash != recorded_hash:
        raise ReplayError(
            f"Progress manifest {manifest_path} changed since the run was recorded "
            f"(recorded {recorded_hash}, found {manifest.hash})"
        )

    if manifest is None and record.progress.scored and record.progress.maximum:
        raise ReplayError(
            f"Run was scored under progress manifest {manifest_path}, but the file is missing; "
            "resuming would silently downgrade progress to unscored."
        )

    tracker = ProgressTracker(manifest=manifest)
    tracker.restore_from(record.progress)
    return tracker


def harness_config_from_record(record: RunRecord):
    """Rebuild the harness configuration recorded in a run's treatment."""
    from llm_quest_benchmark.schemas.config import HarnessConfig

    treatment = record.treatment or {}
    knobs = treatment.get("knobs") or {}
    harness = str(treatment.get("harness") or "")
    if not harness or harness == "unknown":
        raise ReplayError("Run record has no resolvable harness treatment; it cannot be resumed.")

    return HarnessConfig(
        model=str(treatment.get("model") or ""),
        system_template=str(treatment.get("system_prompt") or "system_role.jinja"),
        harness=harness,
        temperature=float(treatment.get("temperature") or 0.0),
        benchmark_id=record.benchmark_id,
        compaction_interval=int(knobs.get("compaction_interval", 50)),
        restore_limit=knobs.get("restore_limit"),
        adaptive_stall_steps=knobs.get("adaptive_stall_steps"),
    )
