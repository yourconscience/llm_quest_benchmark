"""Tests for benchmark markdown reporting."""

import json
from pathlib import Path

from llm_quest_benchmark.core.benchmark_report import render_benchmark_report
from llm_quest_benchmark.harnesses.specs import build_treatment
from llm_quest_benchmark.schemas.records import (
    ProgressState,
    QuestAction,
    QuestSnapshot,
    QuestTransition,
    RunRecord,
)
from llm_quest_benchmark.schemas.response import LLMResponse


def _treatment(model: str, harness: str) -> dict:
    return build_treatment(
        harness=harness,
        model=model,
        temperature=0.4,
        system_template="system_role.jinja",
    ).to_dict()


def _db_run(run_id: int, model: str, harness: str, outcome: str, benchmark_id: str) -> dict:
    treatment = _treatment(model, harness)
    return {
        "id": run_id,
        "quest_file": "quests/Boat.qm",
        "quest_name": "Boat",
        "start_time": "2026-02-15T00:00:00",
        "end_time": "2026-02-15T00:00:10",
        "agent_id": f"{model}_t0.4_{harness}_{treatment['signature'][3:11]}",
        "treatment": json.dumps(treatment),
        "treatment_signature": treatment["signature"],
        "outcome": outcome,
        "reward": 1.0 if outcome == "SUCCESS" else 0.0,
        "run_duration": 10.0,
        "benchmark_id": benchmark_id,
    }


def _write_run_record(agent_id: str, run_id: int, treatment: dict) -> None:
    before = QuestSnapshot(
        location_id="1",
        observation="state",
        choices=[{"id": "11", "text": "go"}, {"id": "12", "text": "stop"}],
        saving={"locationId": 1},
    )
    after = QuestSnapshot(location_id="2", observation="next", choices=[], done=True, game_state="win", saving={})
    record = RunRecord(
        run_id=run_id,
        quest_file="quests/Boat.qm",
        quest_name="Boat",
        quest_checksum="sha256:test",
        quest_language="rus",
        engine_revision="git:test",
        agent_id=agent_id,
        treatment=treatment,
        outcome="SUCCESS",
        reward=1.0,
        run_duration=8.5,
        usage={
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
            "estimated_cost_usd": 0.001,
            "priced_steps": 1,
        },
        progress=ProgressState(current=100.0),
        transitions=[
            QuestTransition(
                index=1,
                before=before,
                action=QuestAction.choose(1, "11", 1735689600000),
                after=after,
                response=LLMResponse(action=1, analysis="short", reasoning="pick go"),
                usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
                progress=ProgressState(current=100.0),
            )
        ],
    )
    run_dir = Path("results") / agent_id / "Boat" / f"run_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_summary.json").write_text(json.dumps(record.to_dict(), ensure_ascii=False), encoding="utf-8")


def test_render_benchmark_report_reads_v2_run_records(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    benchmark_id = "bench_test_1"
    benchmark_dir = Path("results/benchmarks") / benchmark_id
    benchmark_dir.mkdir(parents=True, exist_ok=True)

    run = _db_run(1, "gpt-5-mini", "reasoning_recent", "SUCCESS", benchmark_id)
    summary = {"benchmark_id": benchmark_id, "db_runs": [run], "results": []}
    (benchmark_dir / "benchmark_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_run_record(run["agent_id"], 1, json.loads(run["treatment"]))

    report, selected = render_benchmark_report(
        benchmark_ids=[benchmark_id],
        output_dir="results/benchmarks",
    )

    assert selected == [benchmark_id]
    assert "| Total runs | 1 |" in report
    assert "| Success | 1 |" in report
    assert "| Total tokens | 120 |" in report
    # Model comes from the recorded treatment, not from parsing the agent id.
    assert "| gpt-5-mini |" in report
    assert run["treatment_signature"] in report
    assert "100.0%" in report


def test_render_benchmark_report_splits_same_model_different_harness(tmp_path, monkeypatch):
    """Two agents sharing a model but running under different harnesses must
    appear as two distinct Agent Breakdown rows, not one collapsed row."""
    monkeypatch.chdir(tmp_path)

    benchmark_id = "bench_test_harness_split"
    benchmark_dir = Path("results/benchmarks") / benchmark_id
    benchmark_dir.mkdir(parents=True, exist_ok=True)

    db_runs = [
        _db_run(1, "gpt-5-mini", "reasoning_recent", "SUCCESS", benchmark_id),
        _db_run(2, "gpt-5-mini", "programmatic_memory", "FAILURE", benchmark_id),
    ]
    summary = {"benchmark_id": benchmark_id, "db_runs": db_runs, "results": []}
    (benchmark_dir / "benchmark_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False),
        encoding="utf-8",
    )

    report, selected = render_benchmark_report(
        benchmark_ids=[benchmark_id],
        output_dir="results/benchmarks",
    )

    assert selected == [benchmark_id]
    assert "gpt-5-mini [reasoning_recent]" in report
    assert "gpt-5-mini [programmatic_memory]" in report
    # Neither harness-qualified row should collapse into a bare "gpt-5-mini" row.
    assert "| gpt-5-mini |" not in report
    # Materially different treatments must carry different signatures.
    assert db_runs[0]["treatment_signature"] != db_runs[1]["treatment_signature"]
