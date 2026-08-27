import json
import os
import sqlite3
import tempfile

import pytest

from llm_quest_benchmark.core import logging as logging_module
from llm_quest_benchmark.core.logging import QuestLogger
from llm_quest_benchmark.schemas.records import (
    SCHEMA_VERSION,
    ProgressState,
    QuestAction,
    QuestSnapshot,
    QuestTransition,
)
from llm_quest_benchmark.schemas.response import LLMResponse

TREATMENT = {
    "harness": "reasoning_recent",
    "prompt": "reasoning.jinja",
    "memory": "recent_window",
    "tools": [],
    "loop": "single_call",
    "reasoning": "concise",
    "model": "gpt-5-mini",
    "temperature": 0.4,
    "system_prompt": "system_role.jinja",
    "knobs": {},
    "signature": "t2_0123456789abcdef",
}


@pytest.fixture
def quest_logger():
    """Create a temporary quest logger for testing"""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    logger = QuestLogger(db_path=db_path, debug=True)

    yield logger

    logger.close()
    os.unlink(db_path)


def _snapshot(location_id: str = "room1", observation: str = "You are in a room", choices=None) -> QuestSnapshot:
    return QuestSnapshot(
        location_id=location_id,
        observation=observation,
        choices=choices if choices is not None else [{"id": "11", "text": "Go north"}, {"id": "12", "text": "Go south"}],
        params_state=["HP: 10"],
        saving={"locationId": int(location_id[-1]) if location_id[-1].isdigit() else 1},
    )


def _transition(index: int, choice_index: int, response: LLMResponse | None = None) -> QuestTransition:
    before = _snapshot(location_id=f"room{index}")
    after = _snapshot(location_id=f"room{index + 1}")
    return QuestTransition(
        index=index,
        before=before,
        action=QuestAction.choose(choice_index, before.choices[choice_index - 1]["id"], 1735689600000 + index),
        after=after,
        response=response or LLMResponse(action=choice_index),
        usage={
            "prompt_tokens": response.prompt_tokens if response else 0,
            "completion_tokens": response.completion_tokens if response else 0,
            "total_tokens": response.total_tokens if response else 0,
            "estimated_cost_usd": response.estimated_cost_usd if response else None,
        },
        progress=ProgressState(current=float(index * 10)),
    )


def _start_run(logger: QuestLogger, quest_file: str, agent_id: str = "llm_test-agent") -> int:
    return logger.start_run(
        quest_file=quest_file,
        quest_name=quest_file.split("/")[-1].removesuffix(".qm"),
        quest_checksum="sha256:test",
        quest_language="rus",
        engine_revision="git:test",
        agent_id=agent_id,
        treatment=TREATMENT,
    )


def test_quest_logger_creates_v2_tables(quest_logger):
    quest_logger._init_connection()

    assert os.path.exists(quest_logger.db_path)

    quest_logger._local.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    table_names = [table[0] for table in quest_logger._local.cursor.fetchall()]
    assert "runs" in table_names
    assert "transitions" in table_names
    assert "steps" not in table_names


def test_quest_logger_rejects_legacy_database(tmp_path):
    """A pre-v2 database must fail loudly instead of being silently upgraded."""
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE runs (id INTEGER PRIMARY KEY, quest_name TEXT, outcome TEXT)")
    conn.commit()
    conn.close()

    with pytest.raises(RuntimeError, match="migrate-records"):
        QuestLogger(db_path=str(db_path))


def test_run_metadata_is_written_before_any_transition(quest_logger):
    """Identity, quest provenance, and treatment must exist before execution."""
    run_id = _start_run(quest_logger, "quests/kr_1_ru/Test.qm")

    quest_logger._local.cursor.execute(
        "SELECT schema_version, quest_file, quest_checksum, quest_language, engine_revision, "
        "agent_id, treatment, treatment_signature, outcome FROM runs WHERE id = ?",
        (run_id,),
    )
    row = quest_logger._local.cursor.fetchone()

    assert row[0] == SCHEMA_VERSION
    assert row[1] == "quests/kr_1_ru/Test.qm"
    assert row[2] == "sha256:test"
    assert row[3] == "rus"
    assert row[4] == "git:test"
    assert row[5] == "llm_test-agent"
    assert json.loads(row[6])["harness"] == "reasoning_recent"
    assert row[7] == TREATMENT["signature"]
    assert row[8] is None  # outcome is only known at the end


def test_log_transition_persists_canonical_columns(quest_logger):
    run_id = _start_run(quest_logger, "quests/kr_1_ru/Test.qm")
    transition = _transition(1, 2, LLMResponse(action=2, analysis="south is safer"))

    quest_logger.log_transition(transition)

    quest_logger._local.cursor.execute(
        "SELECT transition_index, before_state, action, after_state, response, provenance, replay_status "
        "FROM transitions WHERE run_id = ?",
        (run_id,),
    )
    row = quest_logger._local.cursor.fetchone()

    assert row[0] == 1
    before = json.loads(row[1])
    assert before["choices"][1]["text"] == "Go south"
    assert before["saving"] is not None
    action = json.loads(row[2])
    assert action["kind"] == "choose"
    assert action["choice_index"] == 2
    assert action["performed_at_ms"] == 1735689600001
    assert json.loads(row[3])["location_id"] == "room2"
    assert "south is safer" in row[4]
    assert row[5] == "runtime"
    assert row[6] == "pending"


def test_run_summary_export_is_schema_v2(tmp_path, monkeypatch, quest_logger):
    monkeypatch.setattr(logging_module, "RESULTS_DIR", tmp_path)

    run_id = _start_run(quest_logger, "quests/kr_1_ru/Test.qm")
    response = LLMResponse(
        action=2,
        analysis="South has better odds",
        reasoning="Avoid immediate danger",
        prompt_tokens=12,
        completion_tokens=5,
        total_tokens=17,
        estimated_cost_usd=0.000123,
    )
    transition = _transition(1, 2, response)
    quest_logger.log_transition(transition)
    quest_logger.finish_run("FAILURE", reward=0.0, terminal_snapshot=transition.after)

    run_dir = tmp_path / "llm_test-agent" / "Test" / f"run_{run_id}"
    summary_path = run_dir / "run_summary.json"
    assert summary_path.exists()

    exported = json.loads(summary_path.read_text(encoding="utf-8"))
    assert exported["schema_version"] == SCHEMA_VERSION
    assert exported["quest"]["checksum"] == "sha256:test"
    assert exported["treatment"]["signature"] == TREATMENT["signature"]
    assert "steps" not in exported
    assert "outcome" not in exported
    assert "metrics" not in exported
    assert "final_snapshot" not in exported

    exported_transition = exported["transitions"][0]
    assert exported_transition["action"]["choice_index"] == 2
    assert exported_transition["before"]["choices"][1]["text"] == "Go south"
    assert exported_transition["after"]["digest"]

    assert exported["usage"]["prompt_tokens"] == 12
    assert exported["usage"]["completion_tokens"] == 5
    assert exported["usage"]["total_tokens"] == 17
    assert exported["usage"]["estimated_cost_usd"] is not None
    diagnostics = exported["transcript_diagnostics"]
    assert diagnostics["total_steps"] == 1
    assert diagnostics["repetition_count"] == 0
    assert diagnostics["bad_decision_count"] == 1
    assert diagnostics["bad_decision_rate"] == 1.0
    assert exported["terminal"]["snapshot"]["location_id"] == "room2"


def test_run_summary_export_tracks_repetition_rate(tmp_path, monkeypatch, quest_logger):
    monkeypatch.setattr(logging_module, "RESULTS_DIR", tmp_path)

    run_id = _start_run(quest_logger, "quests/kr_1_ru/Loop.qm")
    for index, action in enumerate([1, 2, 1, 2, 1, 2], start=1):
        quest_logger.log_transition(_transition(index, action))
    quest_logger.finish_run("SUCCESS", reward=1.0)

    summary_path = tmp_path / "llm_test-agent" / "Loop" / f"run_{run_id}" / "run_summary.json"
    exported = json.loads(summary_path.read_text(encoding="utf-8"))
    diagnostics = exported["transcript_diagnostics"]
    assert diagnostics["total_steps"] == 6
    assert diagnostics["repetition_window"] == 5
    assert diagnostics["repetition_count"] == 4
    assert diagnostics["repetition_rate"] == pytest.approx(4 / 6)
    assert diagnostics["bad_decision_count"] == 0


def test_random_player_exports_v2_json(tmp_path, monkeypatch, quest_logger):
    """Random runs are recorded like every other player type, not suppressed."""
    monkeypatch.setattr(logging_module, "RESULTS_DIR", tmp_path)

    run_id = _start_run(quest_logger, "quests/kr_1_ru/Test.qm", agent_id="random_choice_t0.0_random_choice_abcdef12")
    quest_logger.log_transition(_transition(1, 1))
    quest_logger.finish_run("FAILURE", reward=0.0)

    summary_path = (
        tmp_path / "random_choice_t0.0_random_choice_abcdef12" / "Test" / f"run_{run_id}" / "run_summary.json"
    )
    assert summary_path.exists()
    assert json.loads(summary_path.read_text(encoding="utf-8"))["schema_version"] == SCHEMA_VERSION


def test_metrics_count_restore_transitions_separately(quest_logger):
    transitions = [
        _transition(1, 1),
        QuestTransition(
            index=2,
            before=_snapshot("room2"),
            action=QuestAction.restore(1),
            after=_snapshot("room1"),
        ),
        _transition(3, 2),
    ]

    metrics = QuestLogger.calculate_metrics(transitions, "FAILURE")

    assert metrics["total_steps"] == 2
    assert metrics["restore_transitions"] == 1
    assert metrics["total_transitions"] == 3


def test_finish_run_is_first_write_wins(tmp_path, monkeypatch, quest_logger):
    """Late outcome writes (e.g., from background timeout races) must be ignored."""
    monkeypatch.setattr(logging_module, "RESULTS_DIR", tmp_path)

    run_id = _start_run(quest_logger, "quests/kr_1_ru/Rush.qm")
    timeout_snapshot = _snapshot(location_id="room1", observation="race in progress")
    quest_logger.finish_run("TIMEOUT", reward=0.0, terminal_snapshot=timeout_snapshot)

    late_snapshot = _snapshot(location_id="room9", observation="late success", choices=[])
    quest_logger.finish_run("SUCCESS", reward=1.0, terminal_snapshot=late_snapshot)

    summary_path = tmp_path / "llm_test-agent" / "Rush" / f"run_{run_id}" / "run_summary.json"
    exported = json.loads(summary_path.read_text(encoding="utf-8"))
    assert exported["terminal"]["outcome"] == "TIMEOUT"
    assert exported["terminal"]["reward"] == 0.0
    assert exported["terminal"]["snapshot"]["observation"] == "race in progress"
