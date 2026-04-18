import json
from pathlib import Path

import pytest

from llm_quest_benchmark.core.leaderboard import generate_leaderboard


def test_generate_leaderboard_aggregates_runs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    benchmark_dir = Path("results/benchmarks/bench_1")
    benchmark_dir.mkdir(parents=True, exist_ok=True)

    results = [
        {
            "quest": "quests/ru/Boat.qm",
            "model": "gemini-2.5-flash",
            "temperature": 0.4,
            "template": "stub.jinja",
            "agent_id": "llm_gemini-2.5-flash",
            "attempt": 1,
            "outcome": "SUCCESS",
            "reward": 1.0,
            "error": None,
        },
        {
            "quest": "quests/ru/Boat.qm",
            "model": "gemini-2.5-flash",
            "temperature": 0.4,
            "template": "stub.jinja",
            "agent_id": "llm_gemini-2.5-flash",
            "attempt": 2,
            "outcome": "FAILURE",
            "reward": 0.0,
            "error": None,
        },
        {
            "quest": "quests/Scout.qm",
            "model": "gpt-5-mini",
            "temperature": 0.4,
            "template": "planner.jinja",
            "agent_id": "planner_gpt-5-mini",
            "attempt": 1,
            "outcome": "SUCCESS",
            "reward": 1.0,
            "error": None,
        },
    ]

    db_runs = [
        {
            "id": 1,
            "quest_file": "quests/ru/Boat.qm",
            "quest_name": "Boat",
            "agent_id": "llm_gemini-2.5-flash",
            "agent_config": json.dumps({"model": "gemini-2.5-flash", "action_template": "stub.jinja"}),
            "outcome": "SUCCESS",
        },
        {
            "id": 2,
            "quest_file": "quests/ru/Boat.qm",
            "quest_name": "Boat",
            "agent_id": "llm_gemini-2.5-flash",
            "agent_config": None,
            "outcome": "FAILURE",
        },
        {
            "id": 3,
            "quest_file": "quests/Scout.qm",
            "quest_name": "Scout",
            "agent_id": "planner_gpt-5-mini",
            "agent_config": None,
            "outcome": "SUCCESS",
        },
    ]

    (benchmark_dir / "benchmark_summary.json").write_text(
        json.dumps(
            {
                "benchmark_id": "bench_1",
                "agents": [],
                "results": results,
                "db_runs": db_runs,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    run_summaries = {
        Path("results/llm_gemini-2.5-flash/Boat/run_1/run_summary.json"): {
            "usage": {"total_tokens": 900, "estimated_cost_usd": 0.003},
            "metrics": {"total_steps": 12, "repetition_rate": 0.10},
        },
        Path("results/llm_gemini-2.5-flash/Boat/run_2/run_summary.json"): {
            "usage": {"total_tokens": 600, "estimated_cost_usd": None},
            "metrics": {"total_steps": 18, "repetition_rate": 0.30},
        },
        Path("results/planner_gpt-5-mini/Scout/run_3/run_summary.json"): {
            "usage": {"total_tokens": 1200, "estimated_cost_usd": 0.006},
            "metrics": {"total_steps": 9, "repetition_rate": 0.0},
        },
    }
    for path, payload in run_summaries.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    output_path = Path("site/leaderboard.json")
    leaderboard = generate_leaderboard([str(benchmark_dir)], str(output_path))

    assert output_path.exists()
    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert persisted["benchmark_id"] == "bench_1"

    assert leaderboard["models"] == [
        {"id": "gemini-2.5-flash", "provider": "google", "label": "Gemini 2.5 Flash"},
        {"id": "gpt-5-mini", "provider": "openai", "label": "GPT-5 Mini"},
    ]
    assert leaderboard["modes"] == [
        {"id": "stub", "label": "Baseline (A)"},
        {"id": "planner", "label": "Planner (D)"},
    ]
    assert leaderboard["quests"] == [
        {"id": "Boat", "lang": "RU"},
        {"id": "Scout", "lang": "EN"},
    ]

    boat_row = next(row for row in leaderboard["results"] if row["model"] == "gemini-2.5-flash")
    assert boat_row["mode"] == "stub"
    assert boat_row["quest"] == "Boat"
    assert boat_row["runs"] == 2
    assert boat_row["success_rate"] == pytest.approx(0.5)
    assert boat_row["avg_steps"] == pytest.approx(15.0)
    assert boat_row["avg_tokens"] == pytest.approx(750.0)
    assert boat_row["avg_cost_usd"] == pytest.approx(0.0015)
    assert boat_row["repetition_rate"] == pytest.approx(0.2)

    scout_row = next(row for row in leaderboard["results"] if row["model"] == "gpt-5-mini")
    assert scout_row == {
        "model": "gpt-5-mini",
        "mode": "planner",
        "quest": "Scout",
        "runs": 1,
        "success_rate": 1.0,
        "avg_steps": 9.0,
        "avg_tokens": 1200.0,
        "avg_cost_usd": 0.006,
        "repetition_rate": 0.0,
    }
