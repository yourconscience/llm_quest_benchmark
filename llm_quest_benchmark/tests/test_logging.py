"""Tests for canonical schema-v2 record types"""

import json

import pytest

from llm_quest_benchmark.schemas.records import (
    SCHEMA_VERSION,
    ProgressState,
    QuestAction,
    QuestSnapshot,
    QuestTransition,
    RunRecord,
)
from llm_quest_benchmark.schemas.response import LLMResponse


def _snapshot(**overrides) -> QuestSnapshot:
    payload = {
        "location_id": "room1",
        "observation": "You are in a room",
        "choices": [{"id": "11", "text": "Go north"}, {"id": "12", "text": "Go south"}],
        "params_state": ["HP: 10"],
        "saving": {"locationId": 1, "aleaState": [0.5, 0.25, 0.125, 7]},
    }
    payload.update(overrides)
    return QuestSnapshot(**payload)


def test_snapshot_digest_is_deterministic_and_state_sensitive():
    first = _snapshot()
    second = _snapshot()

    assert first.digest == second.digest
    assert first.digest != _snapshot(location_id="room2").digest
    assert first.digest != _snapshot(params_state=["HP: 9"]).digest
    assert first.digest != _snapshot(saving={"locationId": 1, "aleaState": [0.5, 0.25, 0.125, 8]}).digest


def test_snapshot_agent_observation_appends_params():
    snapshot = _snapshot()

    assert snapshot.agent_observation() == "You are in a room\n\nStatus:\nHP: 10"


def test_choose_transition_round_trips_through_json():
    transition = QuestTransition(
        index=1,
        before=_snapshot(),
        action=QuestAction.choose(choice_index=2, choice_id="12", performed_at_ms=1735689600123),
        after=_snapshot(location_id="room2", observation="A corridor"),
        response=LLMResponse(action=2, reasoning="south is safer", total_tokens=17),
        usage={"prompt_tokens": 12, "completion_tokens": 5, "total_tokens": 17, "estimated_cost_usd": None},
        progress=ProgressState(current=25.0, reached=["mission_accepted"]),
        reasoning_mode="concise",
    )

    restored = QuestTransition.from_dict(json.loads(json.dumps(transition.to_dict())))

    assert restored.action.choice_index == 2
    assert restored.action.choice_id == "12"
    assert restored.action.performed_at_ms == 1735689600123
    assert restored.before.choices == transition.before.choices
    assert restored.before.saving == transition.before.saving
    assert restored.before.digest == transition.before.digest
    assert restored.after.digest == transition.after.digest
    assert restored.response.reasoning == "south is safer"
    assert restored.progress.current == 25.0
    assert restored.reasoning_mode == "concise"
    assert restored.is_replayable


def test_restore_transition_round_trips_and_is_replayable():
    transition = QuestTransition(
        index=4,
        before=_snapshot(location_id="dead_end"),
        action=QuestAction.restore(checkpoint_index=2),
        after=_snapshot(),
    )

    restored = QuestTransition.from_dict(json.loads(json.dumps(transition.to_dict())))

    assert restored.action.is_restore
    assert restored.action.checkpoint_index == 2
    assert restored.is_replayable


def test_transition_without_timestamp_is_not_replayable():
    transition = QuestTransition(
        index=1,
        before=_snapshot(),
        action=QuestAction(kind="choose", choice_index=1, choice_id="11", performed_at_ms=None),
        after=_snapshot(),
    )

    assert not transition.is_replayable


def test_snapshot_without_saving_is_not_resumable():
    assert not _snapshot(saving=None).is_resumable
    assert not QuestSnapshot.unavailable().is_resumable
    assert QuestSnapshot.unavailable().is_unavailable


def test_run_record_rejects_non_v2_payload():
    with pytest.raises(ValueError, match="migrate_records"):
        RunRecord.from_dict({"schema_version": 1, "steps": []})


def test_run_record_round_trips_and_reports_resumability():
    record = RunRecord(
        run_id=7,
        quest_file="quests/Boat.qm",
        quest_name="Boat",
        quest_checksum="sha256:abc",
        quest_language="rus",
        engine_revision="git:deadbeef",
        agent_id="gpt-5-mini_t0.4_reasoning_recent_12345678",
        treatment={"harness": "reasoning_recent", "signature": "t2_abc"},
        outcome="TRUNCATED",
        transitions=[
            QuestTransition(
                index=1,
                before=_snapshot(),
                action=QuestAction.choose(1, "11", 1735689600000),
                after=_snapshot(location_id="room2"),
            )
        ],
    )

    payload = json.loads(json.dumps(record.to_dict()))
    restored = RunRecord.from_dict(payload)

    assert payload["schema_version"] == SCHEMA_VERSION
    assert restored.quest_checksum == "sha256:abc"
    assert restored.treatment_signature == "t2_abc"
    assert restored.is_resumable

    restored.outcome = "FAILURE"
    assert not restored.is_resumable


def test_llm_response_to_dict():
    """LLMResponse dictionary conversion drops unset optional fields"""
    response = LLMResponse(action=1, analysis="Let me think about this", reasoning="Based on the available information")

    data = response.to_dict()
    assert data["action"] == 1
    assert data["analysis"] == "Let me think about this"
    assert data["reasoning"] == "Based on the available information"
