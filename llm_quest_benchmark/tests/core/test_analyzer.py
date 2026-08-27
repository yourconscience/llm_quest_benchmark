"""Tests for the schema-v2 quest run analyzer"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from typer.testing import CliRunner

from llm_quest_benchmark.core.analyzer import analyze_quest_run
from llm_quest_benchmark.core.logging import ensure_v2_schema
from llm_quest_benchmark.executors.cli.commands import app
from llm_quest_benchmark.harnesses.specs import build_treatment
from llm_quest_benchmark.schemas.records import (
    SCHEMA_VERSION,
    QuestAction,
    QuestSnapshot,
    QuestTransition,
)


@contextmanager
def isolated_filesystem():
    previous_cwd = Path.cwd()
    with TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        try:
            yield Path(temp_dir)
        finally:
            os.chdir(previous_cwd)


def _treatment(model: str = "gpt-5-mini", harness: str = "reasoning_recent") -> dict:
    return build_treatment(
        harness=harness,
        model=model,
        temperature=0.4,
        system_template="system_role.jinja",
    ).to_dict()


def _insert_run(conn, quest_name, start_time, end_time, outcome, reward, benchmark_id, treatment):
    cursor = conn.execute(
        """
        INSERT INTO runs (
            schema_version, quest_file, quest_name, quest_checksum, quest_language,
            engine_revision, agent_id, treatment, treatment_signature, benchmark_id,
            start_time, end_time, run_duration, outcome, reward, usage, transcript_diagnostics, progress
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            SCHEMA_VERSION,
            f"quests/{quest_name}",
            quest_name,
            "sha256:test",
            "rus",
            "git:test",
            "llm_test-agent",
            json.dumps(treatment),
            treatment["signature"],
            benchmark_id,
            start_time,
            end_time,
            5.0,
            outcome,
            reward,
            json.dumps({"total_tokens": 10}),
            json.dumps({"total_transitions": 2}),
            json.dumps({"current": 50.0, "maximum": 100.0, "scored": True}),
        ),
    )
    return cursor.lastrowid


def _insert_transition(conn, run_id, index, choice_index):
    before = QuestSnapshot(
        location_id=str(index),
        observation="You are at a trading station.",
        choices=[{"id": "11", "text": "Talk to merchant"}, {"id": "12", "text": "Leave station"}],
        saving={"locationId": index},
    )
    after = QuestSnapshot(location_id=str(index + 1), observation="The merchant greets you.", saving={})
    transition = QuestTransition(
        index=index,
        before=before,
        action=QuestAction.choose(choice_index, before.choices[choice_index - 1]["id"], 1735689600000 + index),
        after=after,
    )
    payload = transition.to_dict()
    conn.execute(
        """
        INSERT INTO transitions (
            run_id, transition_index, before_state, action, after_state,
            response, usage, progress, provenance, replay_status, reasoning_mode
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            index,
            json.dumps(payload["before"]),
            json.dumps(payload["action"]),
            json.dumps(payload["after"]),
            None,
            json.dumps({}),
            json.dumps(payload["progress"]),
            "runtime",
            "pending",
            None,
        ),
    )


def setup_test_db(db_path: Path):
    """Set up a schema-v2 test database with sample data"""
    conn = sqlite3.connect(db_path)
    ensure_v2_schema(conn)

    now = datetime.now()
    treatment = _treatment(model="test-model")

    run1 = _insert_run(conn, "test1.qm", now - timedelta(hours=1), now, "SUCCESS", 1.0, "baseline", treatment)
    run2 = _insert_run(conn, "test1.qm", now - timedelta(minutes=30), now, "FAILURE", 0.0, "baseline", treatment)
    _insert_run(conn, "test2.qm", now, now + timedelta(minutes=30), "SUCCESS", 0.8, "experimental", treatment)

    _insert_transition(conn, run1, 1, 1)
    _insert_transition(conn, run1, 2, 2)
    _insert_transition(conn, run2, 1, 2)

    conn.commit()
    conn.close()


def test_analyze_quest_run(tmp_path):
    """Analyze a specific quest run from the v2 database"""
    db_path = tmp_path / "metrics.db"
    setup_test_db(db_path)

    runner = CliRunner()
    with isolated_filesystem():
        result = runner.invoke(app, ["analyze", "--quest", "test1.qm", "--db", str(db_path), "--debug"])
        assert result.exit_code == 0

        assert "Quest Run Summary" in result.stdout
        assert "test1.qm" in result.stdout
        assert "test-model" in result.stdout
        assert "SUCCESS" in result.stdout
        assert "FAILURE" in result.stdout
        assert "Total Runs: 2" in result.stdout


def test_analyze_benchmark(tmp_path):
    """Analyze benchmark results from the v2 database"""
    db_path = tmp_path / "metrics.db"
    setup_test_db(db_path)

    runner = CliRunner()
    with isolated_filesystem():
        result = runner.invoke(app, ["analyze", "--benchmark", "baseline", "--db", str(db_path)])
        assert result.exit_code == 0

        assert "Benchmark Results" in result.stdout
        assert "Benchmark: baseline" in result.stdout
        assert "Total Runs: 2" in result.stdout
        assert "Success Rate: 50.0%" in result.stdout
        assert "Average Success Reward: 1.00" in result.stdout

        assert "Model Performance" in result.stdout
        assert "test-model" in result.stdout
        assert "50.0%" in result.stdout

        assert "Quest Results" in result.stdout
        assert "test1.qm" in result.stdout


def test_analyze_benchmark_groups_by_treatment_signature(tmp_path):
    """Benchmark analysis groups by canonical treatment, not by harness name"""
    db_path = tmp_path / "metrics.db"
    setup_test_db(db_path)

    runner = CliRunner()
    with isolated_filesystem():
        result = runner.invoke(app, ["analyze", "--benchmark", "baseline", "--db", str(db_path)])
        assert result.exit_code == 0
        assert "Treatment Statistics" in result.stdout
        assert "reasoning_recent" in result.stdout


def test_analyze_specific_benchmark(tmp_path):
    """Analyze a specific benchmark id from the v2 database"""
    db_path = tmp_path / "metrics.db"
    setup_test_db(db_path)

    runner = CliRunner()
    with isolated_filesystem():
        result = runner.invoke(app, ["analyze", "--benchmark", "experimental", "--db", str(db_path)])
        assert result.exit_code == 0

        assert "Benchmark: experimental" in result.stdout
        assert "Total Runs: 1" in result.stdout
        assert "Success Rate: 100.0%" in result.stdout
        assert "Average Success Reward: 0.80" in result.stdout
        assert "test2.qm" in result.stdout


def test_analyze_metrics_returns_transitions(tmp_path):
    """analyze_quest_run returns canonical transitions for each run"""
    db_path = tmp_path / "metrics.db"
    setup_test_db(db_path)

    results = analyze_quest_run("test1.qm", db_path)
    assert results["quest_name"] == "test1.qm"
    assert results["total_runs"] == 2
    assert results["outcomes"]["SUCCESS"] == 1
    assert results["outcomes"]["FAILURE"] == 1
    assert len(results["runs"]) == 2

    run_with_two = next(run for run in results["runs"] if len(run["transitions"]) == 2)
    assert run_with_two["model"] == "test-model"
    assert run_with_two["harness"] == "reasoning_recent"
    assert run_with_two["transitions"][0]["action"]["kind"] == "choose"
    assert run_with_two["transitions"][0]["action"]["performed_at_ms"] == 1735689600001


def test_analyze_no_metrics_dir():
    """analyze with a non-existent database"""
    runner = CliRunner()
    with isolated_filesystem():
        result = runner.invoke(app, ["analyze", "--quest", "test1.qm"])
        assert result.exit_code == 1
        assert "Database not found" in result.output


def test_analyze_empty_metrics_dir(tmp_path):
    """analyze with an empty v2 database"""
    db_path = tmp_path / "metrics.db"
    conn = sqlite3.connect(db_path)
    ensure_v2_schema(conn)
    conn.close()

    runner = CliRunner()
    with isolated_filesystem():
        result = runner.invoke(app, ["analyze", "--quest", "test1.qm", "--db", str(db_path)])
        assert result.exit_code == 1
        assert "No runs found for quest" in result.output


def test_analyze_invalid_file(tmp_path):
    """analyze with an invalid database file"""
    db_path = tmp_path / "metrics.db"
    with open(db_path, "w") as f:
        f.write("invalid data")

    runner = CliRunner()
    with isolated_filesystem():
        result = runner.invoke(app, ["analyze", "--quest", "test1.qm", "--db", str(db_path)])
        assert result.exit_code == 1
        assert "Error analyzing quest run" in result.output


def test_analyze_invalid_benchmark_id(tmp_path):
    """analyze with an unknown benchmark id"""
    db_path = tmp_path / "metrics.db"
    setup_test_db(db_path)

    runner = CliRunner()
    with isolated_filesystem():
        result = runner.invoke(app, ["analyze", "--benchmark", "nonexistent", "--db", str(db_path)])
        assert result.exit_code == 1
        assert "No benchmark data found for nonexistent" in result.output


def test_analyze_run_by_id_prints_transitions(tmp_path):
    """analyze --run-id renders canonical transitions"""
    db_path = tmp_path / "metrics.db"
    setup_test_db(db_path)

    runner = CliRunner()
    with isolated_filesystem():
        result = runner.invoke(app, ["analyze", "--run-id", "1", "--db", str(db_path), "--format", "detail"])
        assert result.exit_code == 0
        assert "Transitions (2 total)" in result.stdout
        assert "Treatment:" in result.stdout
        assert "Talk to merchant" in result.stdout
