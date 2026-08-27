"""Tests for the one-time legacy -> schema-v2 migration."""

import json
import sqlite3

import pytest

from llm_quest_benchmark.core.migration import migrate_legacy_json, migrate_records
from llm_quest_benchmark.schemas.records import SCHEMA_VERSION, RunRecord

LEGACY_AGENT_CONFIG = {
    "model": "gpt-5-mini",
    "harness": "reasoning_recent",
    "temperature": 0.4,
    "system_template": "system_role.jinja",
    "compaction_interval": 50,
}


def _legacy_json(agent_config=LEGACY_AGENT_CONFIG, final_state=True) -> dict:
    return {
        "run_id": 12,
        "quest_file": "quests/Boat.qm",
        "quest_name": "Boat",
        "start_time": "2026-02-15T00:00:00",
        "end_time": "2026-02-15T00:00:20",
        "agent_id": "llm_gpt-5-mini",
        "agent_config": agent_config,
        "outcome": "FAILURE",
        "reward": 0.0,
        "run_duration": 20.0,
        "benchmark_id": "bench_legacy",
        "final_state": (
            {
                "location_id": "9",
                "text": "The end",
                "choices": [],
                "reward": 0.0,
                "done": True,
                "info": {},
            }
            if final_state
            else None
        ),
        "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        "metrics": {"total_steps": 2},
        "steps": [
            {
                "step": 1,
                "location_id": "1",
                "observation": "start",
                "choices": {"1": "go", "2": "stay"},
                "llm_decision": {
                    "analysis": "a",
                    "reasoning": "r",
                    "is_default": False,
                    "parse_mode": "json_direct",
                    "choice": {"1": "go"},
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                    "estimated_cost_usd": 0.001,
                },
            },
            {
                "step": 2,
                "location_id": "2",
                "observation": "middle",
                "choices": {"1": "north", "2": "south"},
                "llm_decision": {
                    "analysis": "b",
                    "reasoning": "r2",
                    "is_default": False,
                    "choice": {"2": "south"},
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                    "estimated_cost_usd": 0.001,
                },
            },
            {
                # Logger-only terminal pseudo-step: state, not an executed action.
                "step": 3,
                "location_id": "9",
                "observation": "The end",
                "choices": {},
                "llm_decision": {"is_default": True, "choice": None},
            },
        ],
    }


def test_legacy_json_maps_deterministically_to_expected_v2_record():
    record = migrate_legacy_json(_legacy_json())

    assert record.schema_version == SCHEMA_VERSION
    assert record.run_id == 12
    assert record.quest_name == "Boat"
    assert record.agent_id == "llm_gpt-5-mini"
    assert record.benchmark_id == "bench_legacy"
    assert record.outcome == "FAILURE"

    # Three legacy rows, but only two executed actions.
    assert len(record.transitions) == 2
    first, second = record.transitions

    assert first.before.location_id == "1"
    assert [c["text"] for c in first.before.choices] == ["go", "stay"]
    assert first.action.choice_index == 1
    assert first.after.location_id == "2"
    assert first.after.observation == "middle"

    assert second.action.choice_index == 2
    # The last after-state comes from final_state when it exists.
    assert second.after.location_id == "9"
    assert second.after.observation == "The end"
    assert second.after.done is True

    # Usage and transcript diagnostics are recomputed from mapped transitions.
    assert record.usage["total_tokens"] == 30
    assert record.usage["prompt_tokens"] == 20
    assert record.transcript_diagnostics["total_steps"] == 2
    assert record.transcript_diagnostics["migrated_from"] == "legacy"


def test_migrated_records_mark_unknowable_fields_and_block_resume():
    record = migrate_legacy_json(_legacy_json())

    for transition in record.transitions:
        assert transition.provenance == "legacy_mapped"
        assert transition.replay_status == "unavailable"
        assert transition.action.performed_at_ms is None
        assert transition.action.choice_id is None
        assert transition.before.saving is None
        assert "saving" in transition.before.unavailable_fields
        assert "choice_ids" in transition.before.unavailable_fields
        assert "params_state" in transition.before.unavailable_fields
        assert not transition.is_replayable

    assert record.quest_language == "unavailable"
    assert record.engine_revision == "unavailable"
    assert not record.is_resumable


def test_missing_post_state_is_marked_unavailable_not_invented():
    payload = _legacy_json(final_state=False)
    # Drop the terminal pseudo-step so the last action has no observed post-state.
    payload["steps"] = payload["steps"][:2]

    record = migrate_legacy_json(payload)

    assert len(record.transitions) == 2
    assert record.transitions[0].after.location_id == "2"  # observed next row
    assert record.transitions[1].after.is_unavailable
    assert record.transitions[1].after.location_id == ""


def test_non_consecutive_rows_do_not_become_a_post_state():
    payload = _legacy_json(final_state=False)
    payload["steps"] = payload["steps"][:2]
    payload["steps"][1]["step"] = 7  # a gap: row 2 is not the observed next state

    record = migrate_legacy_json(payload)

    assert record.transitions[0].after.is_unavailable


def test_unknown_configuration_gets_an_explicit_unknown_treatment():
    record = migrate_legacy_json(_legacy_json(agent_config=None))

    treatment = record.treatment
    assert treatment["harness"] == "unknown"
    assert treatment["prompt"] == "unknown"
    assert treatment["memory"] == "unknown"
    assert treatment["loop"] == "unknown"
    assert treatment["reasoning"] == "unknown"
    assert treatment["signature"].startswith("t2_")


def test_known_configuration_is_resolved_from_the_canonical_registry():
    record = migrate_legacy_json(_legacy_json())

    treatment = record.treatment
    assert treatment["harness"] == "reasoning_recent"
    assert treatment["memory"] == "recent_window"
    assert treatment["loop"] == "single_call"
    assert treatment["prompt"] == "reasoning.jinja"


def test_migrating_a_v2_record_is_rejected():
    with pytest.raises(ValueError, match="already schema v2"):
        migrate_legacy_json({"schema_version": SCHEMA_VERSION, "transitions": []})


def test_migrate_json_tree_writes_v2_records(tmp_path):
    source = tmp_path / "results" / "llm_gpt-5-mini" / "Boat" / "run_12"
    source.mkdir(parents=True)
    (source / "run_summary.json").write_text(json.dumps(_legacy_json()), encoding="utf-8")

    output = tmp_path / "results_v2"
    report = migrate_records(tmp_path / "results", output)

    assert report.kind == "json"
    assert report.runs_migrated == 1
    assert report.transitions_migrated == 2
    assert report.resumable_runs == 0

    migrated_path = output / "llm_gpt-5-mini" / "Boat" / "run_12" / "run_summary.json"
    assert migrated_path.exists()
    record = RunRecord.from_dict(json.loads(migrated_path.read_text(encoding="utf-8")))
    assert len(record.transitions) == 2


def _legacy_sqlite(path) -> None:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quest_file TEXT, quest_name TEXT, start_time TIMESTAMP, end_time TIMESTAMP,
            agent_id TEXT, agent_config TEXT, outcome TEXT, reward REAL,
            run_duration REAL, benchmark_id TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER, step INTEGER, location_id TEXT, observation TEXT,
            choices TEXT, action TEXT, llm_response TEXT
        )
        """
    )
    cursor = conn.execute(
        """
        INSERT INTO runs (quest_file, quest_name, start_time, end_time, agent_id, agent_config,
                          outcome, reward, run_duration, benchmark_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "quests/Boat.qm",
            "Boat",
            "2026-02-15T00:00:00",
            "2026-02-15T00:00:20",
            "llm_gpt-5-mini",
            json.dumps(LEGACY_AGENT_CONFIG),
            "FAILURE",
            0.0,
            20.0,
            "bench_legacy",
        ),
    )
    run_id = cursor.lastrowid
    choices = json.dumps([{"id": "11", "text": "go"}, {"id": "12", "text": "stay"}])
    conn.executemany(
        "INSERT INTO steps (run_id, step, location_id, observation, choices, action, llm_response) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            # The model proposed 2, but the runner clamped the executed action to 1.
            (run_id, 1, "1", "start", choices, "1", json.dumps({"action": 2, "reasoning": "r"})),
            (run_id, 2, "2", "middle", choices, "2", json.dumps({"action": 2, "reasoning": "r2"})),
            (run_id, 3, "9", "The end", json.dumps([]), "FAILURE", None),
        ],
    )
    conn.commit()
    conn.close()


def test_migrate_legacy_sqlite_creates_a_v2_database(tmp_path):
    source = tmp_path / "legacy.db"
    _legacy_sqlite(source)
    output = tmp_path / "metrics_v2.db"

    report = migrate_records(source, output)

    assert report.kind == "sqlite"
    assert report.runs_migrated == 1
    assert report.transitions_migrated == 2
    assert report.resumable_runs == 0

    conn = sqlite3.connect(output)
    try:
        run = conn.execute(
            "SELECT schema_version, quest_name, agent_id, treatment_signature, outcome FROM runs"
        ).fetchone()
        assert run[0] == SCHEMA_VERSION
        assert run[1] == "Boat"
        assert run[2] == "llm_gpt-5-mini"
        assert run[3].startswith("t2_")
        assert run[4] == "FAILURE"

        transitions = conn.execute(
            "SELECT transition_index, action, provenance, replay_status FROM transitions ORDER BY transition_index"
        ).fetchall()
        assert len(transitions) == 2
        first_action = json.loads(transitions[0][1])
        # SQLite's steps.action wins: it is the runner-executed action, while
        # the model proposal in llm_response could disagree.
        assert first_action["choice_index"] == 1
        assert first_action["choice_id"] == "11"  # engine jump ids survive in SQLite
        assert first_action["performed_at_ms"] is None
        assert transitions[0][2] == "legacy_mapped"
        assert transitions[0][3] == "unavailable"
    finally:
        conn.close()


def test_migrate_rejects_an_existing_output_database(tmp_path):
    source = tmp_path / "legacy.db"
    _legacy_sqlite(source)
    output = tmp_path / "metrics_v2.db"
    output.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="output already exists"):
        migrate_records(source, output)


def test_migrate_rejects_a_v2_source_database(tmp_path):
    from llm_quest_benchmark.core.logging import ensure_v2_schema

    source = tmp_path / "already_v2.db"
    conn = sqlite3.connect(source)
    ensure_v2_schema(conn)
    conn.close()

    with pytest.raises(ValueError, match="already schema v2"):
        migrate_records(source, tmp_path / "out.db")


def test_migrate_missing_source_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        migrate_records(tmp_path / "nope", tmp_path / "out")
