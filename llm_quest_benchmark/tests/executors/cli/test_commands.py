"""Tests for CLI commands"""

import json
import sqlite3
from pathlib import Path
from unittest.mock import Mock

from typer.testing import CliRunner

from llm_quest_benchmark.constants import DEFAULT_QUEST
from llm_quest_benchmark.executors.cli import commands
from llm_quest_benchmark.executors.cli.commands import app
from llm_quest_benchmark.harnesses.specs import build_treatment
from llm_quest_benchmark.schemas.records import (
    ProgressState,
    QuestAction,
    QuestSnapshot,
    QuestTransition,
    RunRecord,
)
from llm_quest_benchmark.schemas.response import LLMResponse

runner = CliRunner()


def _record(outcome: str = "FAILURE", resumable: bool = False) -> RunRecord:
    before = QuestSnapshot(
        location_id="1",
        observation="State one",
        choices=[{"id": "11", "text": "Go left"}, {"id": "12", "text": "Go right"}],
        saving={"locationId": 1} if resumable else None,
    )
    after = QuestSnapshot(
        location_id="2",
        observation="State two",
        choices=[],
        done=True,
        game_state="fail",
        saving={"locationId": 2} if resumable else None,
    )
    return RunRecord(
        run_id=1,
        quest_file="quests/Boat.qm",
        quest_name="TestQuest",
        quest_checksum="sha256:test",
        quest_language="rus",
        engine_revision="git:test",
        agent_id="llm_test",
        treatment=build_treatment("reasoning_recent", "gpt-5-mini", 0.4, "system_role.jinja").to_dict(),
        outcome=outcome,
        progress=ProgressState(current=40.0),
        terminal_snapshot=after,
        transitions=[
            QuestTransition(
                index=1,
                before=before,
                action=QuestAction.choose(2, "12", 1735689600000),
                after=after,
                response=LLMResponse(action=2, analysis="Need progress", reasoning="Right seems safer"),
                progress=ProgressState(current=40.0),
            )
        ],
    )


def _write_record(path: Path, record: RunRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record.to_dict(), ensure_ascii=False), encoding="utf-8")


def test_version():
    """Test version command"""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "llm-quest version" in result.stdout


def test_run_quest():
    """Test running a quest with random player"""
    result = runner.invoke(
        app,
        ["run", "--quest", str(DEFAULT_QUEST), "--model", "random_choice", "--harness", "random_choice", "--debug"],
    )
    assert result.exit_code in [0, 1, 2]


def test_run_quest_invalid_args():
    """Test run command with invalid arguments"""
    result = runner.invoke(app, ["run", "--quest", str(DEFAULT_QUEST), "--model", "invalid-model"])
    assert result.exit_code == 2

    result = runner.invoke(
        app, ["run", "--quest", "nonexistent.qm", "--model", "random_choice", "--harness", "random_choice"]
    )
    assert result.exit_code == 2


def test_run_rejects_restore_limit_for_other_harnesses():
    result = runner.invoke(
        app,
        [
            "run",
            "--quest",
            str(DEFAULT_QUEST),
            "--model",
            "gpt-5-mini",
            "--harness",
            "reasoning_recent",
            "--restore-limit",
            "2",
        ],
    )
    assert result.exit_code == 2


def test_run_rejects_resuming_a_non_resumable_record(tmp_path):
    path = tmp_path / "run_summary.json"
    _write_record(path, _record(outcome="FAILURE"))

    result = runner.invoke(app, ["run", "--resume-from", str(path)])

    assert result.exit_code == 1
    assert "not resumable" in result.output


def test_analyze_invalid_input():
    """Test analyze command with invalid input"""
    result = runner.invoke(app, ["analyze"])
    assert result.exit_code == 1
    assert "Must specify one of: --quest, --benchmark, --run-id, or --last" in result.output


def test_benchmark_missing_config():
    """Test benchmark command with missing config"""
    result = runner.invoke(app, ["benchmark", "--config", "nonexistent.yaml"])
    assert result.exit_code == 1
    assert "Config file does not exist" in result.output


def test_analyze_run_with_run_summary_path(tmp_path):
    """analyze-run against an explicit schema-v2 run_summary path."""
    summary_path = tmp_path / "run_summary.json"
    _write_record(summary_path, _record())

    result = runner.invoke(app, ["analyze-run", "--run-summary", str(summary_path)])
    assert result.exit_code == 0
    assert "Decision Steps: 1" in result.stdout
    assert "selected [2:Go right]" in result.stdout
    assert "Treatment: t2_" in result.stdout
    assert "Progress: 40.0%" in result.stdout


def test_analyze_run_rejects_legacy_records(tmp_path):
    """A pre-v2 run summary must point at the migration command, not be parsed."""
    summary_path = tmp_path / "run_summary.json"
    summary_path.write_text(json.dumps({"run_id": 1, "steps": []}), encoding="utf-8")

    result = runner.invoke(app, ["analyze-run", "--run-summary", str(summary_path)])

    assert result.exit_code == 2
    assert "migrate-records" in result.output


def test_analyze_run_autolocates_latest_run(monkeypatch, tmp_path):
    """analyze-run latest-run discovery with --agent and --quest."""
    monkeypatch.chdir(tmp_path)
    _write_record(
        tmp_path / "results" / "llm_test" / "QuestA" / "run_42" / "run_summary.json",
        _record(outcome="SUCCESS"),
    )

    result = runner.invoke(app, ["analyze-run", "--agent", "llm_test", "--quest", "QuestA"])
    assert result.exit_code == 0
    assert "Outcome: SUCCESS" in result.stdout


def test_migrate_records_converts_a_legacy_tree(tmp_path):
    legacy = tmp_path / "results" / "llm_old" / "Boat" / "run_3" / "run_summary.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(
        json.dumps(
            {
                "run_id": 3,
                "quest_file": "quests/Boat.qm",
                "quest_name": "Boat",
                "agent_id": "llm_old",
                "agent_config": {"model": "gpt-5-mini", "harness": "reasoning_recent", "temperature": 0.4},
                "outcome": "FAILURE",
                "steps": [
                    {
                        "step": 1,
                        "location_id": "1",
                        "observation": "start",
                        "choices": {"1": "go", "2": "stay"},
                        "llm_decision": {"choice": {"1": "go"}, "is_default": False},
                    },
                    {"step": 2, "location_id": "9", "observation": "end", "choices": {}, "llm_decision": {}},
                ],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "results_v2"

    result = runner.invoke(
        app, ["migrate-records", "--source", str(tmp_path / "results"), "--output", str(output)]
    )

    assert result.exit_code == 0
    assert "Migrated 1 runs" in result.stdout
    assert "Resumable runs: 0" in result.stdout
    migrated = output / "llm_old" / "Boat" / "run_3" / "run_summary.json"
    assert migrated.exists()
    assert json.loads(migrated.read_text(encoding="utf-8"))["schema_version"] == 2


def test_migrate_records_reports_a_missing_source(tmp_path):
    result = runner.invoke(
        app, ["migrate-records", "--source", str(tmp_path / "nope"), "--output", str(tmp_path / "out")]
    )

    assert result.exit_code == 1
    assert "Migration failed" in result.output


def test_cleanup_counts_transitions(tmp_path):
    from llm_quest_benchmark.core.logging import ensure_v2_schema

    db_path = tmp_path / "metrics.db"
    conn = sqlite3.connect(db_path)
    ensure_v2_schema(conn)
    conn.close()

    result = runner.invoke(app, ["cleanup", "--db-path", str(db_path), "--all", "--no-backup"])

    assert result.exit_code == 0
    assert "transitions" in result.stdout


def test_download_quests_command_prints_summary(monkeypatch):
    """Test quest downloader wrapper prints collection counts."""
    fake_run = Mock()
    fake_registry = Mock()
    fake_collections = [
        {"collection": "sr_2_1_2121_eng", "language": "EN", "count": 35},
        {"collection": "sr_2_dominators_ru", "language": "RU", "count": 35},
    ]

    monkeypatch.setattr(commands.subprocess, "run", fake_run)
    monkeypatch.setattr(commands, "get_registry", fake_registry)
    monkeypatch.setattr(commands, "_count_quest_collections", lambda _: fake_collections)

    result = runner.invoke(app, ["download-quests"])
    assert result.exit_code == 0
    fake_run.assert_called_once()
    fake_registry.assert_called_once_with(reset_cache=True)
    assert "Quest counts by collection:" in result.stdout
    assert "sr_2_1_2121_eng (EN): 35 .qm/.qmm files" in result.stdout
    assert "Totals: EN=35 RU=35 TOTAL=70" in result.stdout
