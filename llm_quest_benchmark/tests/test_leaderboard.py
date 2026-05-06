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
    leaderboard = generate_leaderboard(
        [str(benchmark_dir)],
        str(output_path),
        min_runs=0,
        public_model_ids=None,
    )

    assert output_path.exists()
    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert persisted["benchmark_id"] == "bench_1"

    assert leaderboard["models"] == [
        {"id": "gemini-2.5-flash", "provider": "google", "label": "Gemini 2.5 Flash"},
        {"id": "gpt-5-mini", "provider": "openai", "label": "GPT-5 Mini"},
    ]
    assert leaderboard["modes"] == [
        {"id": "minimal_prompt", "label": "Minimal prompt"},
        {"id": "planner_loop", "label": "Planner loop"},
    ]
    assert leaderboard["quests"] == [
        {"id": "Boat", "lang": "RU"},
        {"id": "Scout", "lang": "EN"},
    ]

    boat_row = next(row for row in leaderboard["results"] if row["model"] == "gemini-2.5-flash")
    assert boat_row["mode"] == "minimal_prompt"
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
        "mode": "planner_loop",
        "quest": "Scout",
        "runs": 1,
        "success_rate": 1.0,
        "avg_steps": 9.0,
        "avg_tokens": 1200.0,
        "avg_cost_usd": 0.006,
        "repetition_rate": 0.0,
    }


def test_public_leaderboard_taxonomy_has_no_legacy_labels():
    repo_root = Path(__file__).resolve().parents[2]
    old_labels = [
        f"{name} ({letter})"
        for name, letter in [
            ("Baseline", "A"),
            ("Prompted", "B"),
            ("Knowledge", "C"),
            ("Planner", "D"),
            ("Tool-aug", "E"),
        ]
    ]

    index_html = (repo_root / "site/index.html").read_text(encoding="utf-8")
    for label in old_labels:
        assert label not in index_html
    assert "leaderboard.json?v=" in index_html

    leaderboard = json.loads((repo_root / "site/leaderboard.json").read_text(encoding="utf-8"))
    mode_labels = {mode["label"] for mode in leaderboard["modes"]}
    assert mode_labels == {
        "Minimal prompt",
        "Short-context reasoning",
        "Full-history reasoning",
        "Compact memory / memo",
        "Prompt hints",
        "Tools + compact memory",
        "Tools + hints + compact memory",
        "Planner loop",
    }
    for label in old_labels:
        assert label not in json.dumps(leaderboard, ensure_ascii=False)


def test_generate_leaderboard_filters_public_slice(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    benchmark_dir = Path("results/benchmarks/bench_public")
    benchmark_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for model in ["model-a", "model-b", "model-c"]:
        for quest in ["Core", "Solo"]:
            rows.append(
                {
                    "quest": f"quests/{quest}.qm",
                    "model": model,
                    "template": "stub.jinja",
                    "agent_id": model,
                    "attempt": 1,
                    "outcome": "SUCCESS",
                    "reward": 1.0,
                    "error": None,
                }
            )
    rows.append(
        {
            "quest": "quests/Core.qm",
            "model": "low-coverage",
            "template": "stub.jinja",
            "agent_id": "low-coverage",
            "attempt": 1,
            "outcome": "SUCCESS",
            "reward": 1.0,
            "error": None,
        }
    )
    rows = [row for row in rows if not (row["quest"] == "quests/Solo.qm" and row["model"] != "model-a")]

    (benchmark_dir / "benchmark_summary.json").write_text(
        json.dumps({"benchmark_id": "bench_public", "agents": [], "results": rows, "db_runs": []}),
        encoding="utf-8",
    )

    leaderboard = generate_leaderboard(
        [str(benchmark_dir)],
        "site/leaderboard.json",
        min_runs=1,
        public_model_ids=["model-a", "model-b", "model-c"],
    )

    assert [model["id"] for model in leaderboard["models"]] == ["model-a", "model-b", "model-c"]
    assert leaderboard["scope"]["min_models_per_quest"] == 3
    assert [quest["id"] for quest in leaderboard["quests"]] == ["Core"]
    assert {row["quest"] for row in leaderboard["results"]} == {"Core"}
    assert {row["model"] for row in leaderboard["results"]} == {"model-a", "model-b", "model-c"}


def test_generate_leaderboard_matches_db_runs_by_identifiers(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    benchmark_dir = Path("results/benchmarks/bench_match")
    benchmark_dir.mkdir(parents=True, exist_ok=True)

    results = [
        {
            "quest": "quests/Alpha.qm",
            "model": "gpt-5-mini",
            "template": "stub.jinja",
            "agent_id": "llm_gpt-5-mini",
            "outcome": "SUCCESS",
        },
        {
            "quest": "quests/Beta.qm",
            "model": "gpt-5-mini",
            "template": "stub.jinja",
            "agent_id": "llm_gpt-5-mini",
            "outcome": "SUCCESS",
        },
    ]
    db_runs = [
        {
            "id": 20,
            "quest_file": "quests/Beta.qm",
            "quest_name": "Beta",
            "agent_id": "llm_gpt-5-mini",
            "agent_config": json.dumps(
                {"model": "gpt-5-mini", "action_template": "reasoning.jinja", "memory_mode": "full_transcript"}
            ),
            "outcome": "SUCCESS",
        },
        {
            "id": 10,
            "quest_file": "quests/Alpha.qm",
            "quest_name": "Alpha",
            "agent_id": "llm_gpt-5-mini",
            "agent_config": json.dumps(
                {"model": "gpt-5-mini", "action_template": "loop_aware_reasoning.jinja", "memory_mode": "compaction"}
            ),
            "outcome": "SUCCESS",
        },
    ]
    (benchmark_dir / "benchmark_summary.json").write_text(
        json.dumps({"benchmark_id": "bench_match", "agents": [], "results": results, "db_runs": db_runs}),
        encoding="utf-8",
    )

    for run_id, quest_name, total_steps in [(10, "Alpha", 10), (20, "Beta", 20)]:
        path = Path("results/llm_gpt-5-mini") / quest_name / f"run_{run_id}" / "run_summary.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"usage": {"total_tokens": total_steps}, "metrics": {"total_steps": total_steps}}),
            encoding="utf-8",
        )

    leaderboard = generate_leaderboard(
        [str(benchmark_dir)],
        "site/leaderboard.json",
        min_runs=0,
        public_model_ids=None,
    )

    rows = {(row["quest"], row["mode"]): row for row in leaderboard["results"]}
    assert rows[("Alpha", "compact_memory_memo")]["avg_steps"] == 10.0
    assert rows[("Beta", "full_history_reasoning")]["avg_steps"] == 20.0
