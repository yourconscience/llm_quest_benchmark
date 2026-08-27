"""Tests for deterministic replay verification and resume assembly."""

import copy
import json
from pathlib import Path

import pytest

from llm_quest_benchmark.core.replay import (
    ReplayError,
    harness_config_from_record,
    replay_record,
    restore_progress_tracker,
    verify_environment,
)
from llm_quest_benchmark.harnesses.specs import build_treatment
from llm_quest_benchmark.schemas.records import (
    ProgressState,
    QuestAction,
    QuestSnapshot,
    QuestTransition,
    RunRecord,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
BOAT = str(REPO_ROOT / "quests" / "Boat.qm")


def _snapshot(location_id: str, timestamp: int, choices=None) -> QuestSnapshot:
    """Snapshot whose content depends on the transition timestamp.

    Real quests can branch on the timestamp handed to performJump, so the fake
    engine mirrors that: a replayed timestamp change must change the state.
    """
    return QuestSnapshot(
        location_id=location_id,
        observation=f"At {location_id} (t={timestamp})",
        choices=choices if choices is not None else [{"id": "11", "text": "A"}, {"id": "12", "text": "B"}],
        saving={"locationId": location_id, "t": timestamp},
    )


class _FakeEngine:
    """Deterministic fake engine: state is a function of action and timestamp."""

    def __init__(self):
        self.quest_file = BOAT
        self.language = "rus"
        self.forced_stop_reason = None
        self._snapshot = None
        self.calls = []

    def reset(self):
        self._snapshot = _snapshot("start", 0)
        return self._snapshot

    def step(self, choice_index, performed_at_ms):
        self.calls.append((choice_index, performed_at_ms))
        location = f"{self._snapshot.location_id}>{choice_index}"
        self._snapshot = _snapshot(location, performed_at_ms)
        return self._snapshot

    def restore(self, snapshot):
        if snapshot.saving is None:
            raise ValueError("Cannot restore a snapshot without a full engine saving")
        self._snapshot = snapshot
        return snapshot

    def close(self):
        return None


def _recorded_run() -> tuple[RunRecord, _FakeEngine]:
    """Execute a short run against the fake engine and record it."""
    engine = _FakeEngine()
    snapshot = engine.reset()
    transitions = []
    for index, (choice, timestamp) in enumerate([(1, 1000), (2, 2000), (1, 3000)], start=1):
        before = snapshot
        after = engine.step(choice, timestamp)
        transitions.append(
            QuestTransition(
                index=index,
                before=before,
                action=QuestAction.choose(choice, before.choices[choice - 1]["id"], timestamp),
                after=after,
            )
        )
        snapshot = after

    record = RunRecord(
        run_id=1,
        quest_file=BOAT,
        quest_name="Boat",
        quest_checksum="",
        quest_language="rus",
        engine_revision="",
        agent_id="agent",
        treatment=build_treatment("reasoning_recent", "gpt-5-mini", 0.4, "system_role.jinja").to_dict(),
        outcome="TRUNCATED",
        transitions=transitions,
        progress=ProgressState(current=30.0, reached=["a"]),
    )
    return record, engine


def test_replay_of_an_unchanged_record_verifies_every_transition():
    record, _ = _recorded_run()

    result = replay_record(_FakeEngine(), record)

    assert result.verified_transitions == 3
    assert result.snapshot.digest == record.transitions[-1].after.digest
    # Checkpoints are the active branch: the start plus one per executed choose.
    assert len(result.checkpoints) == 4


def test_replay_reexecutes_the_recorded_timestamps():
    record, _ = _recorded_run()
    engine = _FakeEngine()

    replay_record(engine, record)

    assert engine.calls == [(1, 1000), (2, 2000), (1, 3000)]


def test_replay_detects_a_changed_action():
    """Even a self-consistent action edit is caught by the resulting state."""
    record, _ = _recorded_run()
    record.transitions[1].action.choice_index = 1
    record.transitions[1].action.choice_id = "11"

    with pytest.raises(ReplayError, match="after-state diverged"):
        replay_record(_FakeEngine(), record)


def test_replay_detects_a_changed_timestamp():
    record, _ = _recorded_run()
    record.transitions[1].action.performed_at_ms = 2999

    with pytest.raises(ReplayError, match="after-state diverged"):
        replay_record(_FakeEngine(), record)


def test_replay_detects_a_changed_choice_id():
    record, _ = _recorded_run()
    record.transitions[0].action.choice_id = "999"

    with pytest.raises(ReplayError, match="choice id diverged"):
        replay_record(_FakeEngine(), record)


def test_replay_detects_a_mutated_resulting_state():
    record, _ = _recorded_run()
    record.transitions[2].after = QuestSnapshot(
        location_id="tampered", observation="tampered", saving={"locationId": "tampered"}
    )

    with pytest.raises(ReplayError, match="after-state diverged"):
        replay_record(_FakeEngine(), record)


def test_replay_detects_a_mutated_before_state():
    record, _ = _recorded_run()
    record.transitions[1].before = QuestSnapshot(
        location_id="tampered", observation="tampered", saving={"locationId": "tampered"}
    )

    with pytest.raises(ReplayError, match="before-state diverged"):
        replay_record(_FakeEngine(), record)


def test_replay_rejects_non_replayable_transitions():
    record, _ = _recorded_run()
    record.transitions[0].provenance = "legacy_mapped"
    record.transitions[0].replay_status = "unavailable"

    with pytest.raises(ReplayError, match="not replayable"):
        replay_record(_FakeEngine(), record)


def test_replay_reproduces_restores_and_truncates_the_active_branch():
    record, engine = _recorded_run()
    # Append a restore back to the first checkpoint, then one more choose.
    current = record.transitions[-1].after
    target = record.transitions[0].before
    engine.restore(target)
    record.transitions.append(
        QuestTransition(
            index=4,
            before=current,
            action=QuestAction.restore(1),
            after=target,
        )
    )
    after = engine.step(2, 4000)
    record.transitions.append(
        QuestTransition(
            index=5,
            before=target,
            action=QuestAction.choose(2, "12", 4000),
            after=after,
        )
    )

    result = replay_record(_FakeEngine(), record)

    assert result.verified_transitions == 5
    assert result.snapshot.digest == after.digest
    # After restoring to checkpoint 1 and taking one step, the branch is 2 deep.
    assert len(result.checkpoints) == 2


def test_verify_environment_detects_a_changed_quest():
    record, _ = _recorded_run()
    record.quest_checksum = "sha256:not-this-quest"

    with pytest.raises(ReplayError, match="Quest checksum mismatch"):
        verify_environment(record, BOAT)


def test_verify_environment_detects_a_changed_engine():
    record, _ = _recorded_run()
    record.engine_revision = "git:0000000000000000000000000000000000000000"

    with pytest.raises(ReplayError, match="Engine revision mismatch"):
        verify_environment(record, BOAT)


def test_harness_config_is_rebuilt_from_the_recorded_treatment():
    record, _ = _recorded_run()

    config = harness_config_from_record(record)

    assert config.harness == "reasoning_recent"
    assert config.model == "gpt-5-mini"
    assert config.temperature == pytest.approx(0.4)
    assert config.system_template == "system_role.jinja"
    # Rebuilding must reproduce the exact recorded signature.
    assert config.treatment().signature == record.treatment_signature


def test_harness_config_rejects_an_unknown_migrated_treatment():
    record, _ = _recorded_run()
    record.treatment = {"harness": "unknown", "model": "unavailable"}

    with pytest.raises(ReplayError, match="no resolvable harness treatment"):
        harness_config_from_record(record)


def test_backtracking_knobs_survive_the_record_round_trip():
    record, _ = _recorded_run()
    record.treatment = build_treatment(
        "backtracking", "gpt-5-mini", 0.4, "system_role.jinja", {"restore_limit": 2, "compaction_interval": 10}
    ).to_dict()

    config = harness_config_from_record(record)

    assert config.harness == "backtracking"
    assert config.restore_limit == 2
    assert config.compaction_interval == 10


def test_restore_progress_tracker_recovers_the_recorded_state(tmp_path):
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        'quest: Demo\nversion: 1\nmilestones:\n  - id: a\n    percent: 30\n    match:\n      location_id: ["x"]\n',
        encoding="utf-8",
    )
    record, _ = _recorded_run()
    record.progress = ProgressState(current=30.0, reached=["a"], stalled_transitions=2, manifest=str(manifest))

    tracker = restore_progress_tracker(record)

    assert tracker.manifest is not None
    assert tracker.state().current == pytest.approx(30.0)
    assert tracker.state().reached == ["a"]
    assert tracker.state().stalled_transitions == 2


def test_record_json_round_trip_survives_replay():
    """A record read back from disk must replay exactly like the in-memory one."""
    record, _ = _recorded_run()
    reloaded = RunRecord.from_dict(json.loads(json.dumps(record.to_dict())))

    result = replay_record(_FakeEngine(), reloaded)

    assert result.verified_transitions == len(record.transitions)
    assert result.snapshot.digest == record.transitions[-1].after.digest
    assert copy.deepcopy(reloaded.to_dict()) == record.to_dict()
