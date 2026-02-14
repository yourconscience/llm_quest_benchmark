"""Tests for benchmark markdown reporting."""
import json
from pathlib import Path

from llm_quest_benchmark.core.benchmark_report import render_benchmark_report


def test_render_benchmark_report_reads_run_summaries(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    benchmark_id = "bench_test_1"
    benchmark_dir = Path("results/benchmarks") / benchmark_id
    benchmark_dir.mkdir(parents=True, exist_ok=True)

    db_runs = [
        {
            "id": 1,
            "quest_file": "quests/Boat.qm",
            "quest_name": "Boat",
            "start_time": "2026-02-15T00:00:00",
            "end_time": "2026-02-15T00:00:10",
            "agent_id": "llm_gpt-5-mini",
            "agent_config": json.dumps({"model": "gpt-5-mini"}),
            "outcome": "SUCCESS",
            "reward": 1.0,
            "run_duration": 10.0,
            "benchmark_id": benchmark_id,
        }
    ]
    summary = {"benchmark_id": benchmark_id, "db_runs": db_runs, "results": []}
    (benchmark_dir / "benchmark_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False),
        encoding="utf-8",
    )

    run_summary_dir = Path("results/llm_gpt-5-mini/Boat/run_1")
    run_summary_dir.mkdir(parents=True, exist_ok=True)
    run_summary = {
        "run_id": 1,
        "quest_name": "Boat",
        "agent_id": "llm_gpt-5-mini",
        "outcome": "SUCCESS",
        "run_duration": 8.5,
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
            "estimated_cost_usd": 0.001,
            "priced_steps": 1,
        },
        "steps": [
            {
                "step": 1,
                "observation": "state",
                "choices": {"1": "go", "2": "stop"},
                "llm_decision": {
                    "analysis": "short",
                    "reasoning": "pick go",
                    "is_default": False,
                    "choice": {"1": "go"},
                },
            }
        ],
    }
    (run_summary_dir / "run_summary.json").write_text(
        json.dumps(run_summary, ensure_ascii=False),
        encoding="utf-8",
    )

    report, selected = render_benchmark_report(
        benchmark_ids=[benchmark_id],
        output_dir="results/benchmarks",
    )

    assert selected == [benchmark_id]
    assert "| Total runs | 1 |" in report
    assert "| Success | 1 |" in report
    assert "| Total tokens | 120 |" in report
    assert "| gpt-5-mini | 1 | 1 | 0 | 0 | 0 | 100.0% | 120 | 0.001000 | 0.0% |" in report
