import json
from pathlib import Path

import pytest

from llm_quest_benchmark.core.leaderboard import generate_leaderboard
from llm_quest_benchmark.harnesses.specs import build_treatment


def _treatment(harness: str, model: str) -> dict:
    return build_treatment(
        harness=harness,
        model=model,
        temperature=0.4,
        system_template="system_role.jinja",
    ).to_dict()


def _result_row(quest: str, model: str, harness: str, agent_id: str, outcome: str = "SUCCESS", **extra) -> dict:
    treatment = _treatment(harness, model)
    row = {
        "quest": quest,
        "model": model,
        "temperature": 0.4,
        "harness": harness,
        "treatment": treatment,
        "treatment_signature": treatment["signature"],
        "agent_id": agent_id,
        "attempt": 1,
        "outcome": outcome,
        "reward": 1.0 if outcome == "SUCCESS" else 0.0,
        "error": None,
    }
    row.update(extra)
    return row


def _db_run(
    run_id: int,
    quest_file: str,
    quest_name: str,
    agent_id: str,
    harness: str,
    model: str,
    outcome: str,
    usage: dict | None = None,
    diagnostics: dict | None = None,
    progress: dict | None = None,
) -> dict:
    treatment = _treatment(harness, model)
    return {
        "id": run_id,
        "schema_version": 2,
        "quest_file": quest_file,
        "quest_name": quest_name,
        "agent_id": agent_id,
        "treatment": treatment,
        "treatment_signature": treatment["signature"],
        "outcome": outcome,
        "usage": usage or {},
        "transcript_diagnostics": diagnostics or {},
        "progress": progress or {},
    }


def test_generate_leaderboard_aggregates_runs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    benchmark_dir = Path("results/benchmarks/bench_1")
    benchmark_dir.mkdir(parents=True, exist_ok=True)

    results = [
        _result_row("quests/ru/Boat.qm", "gemini-2.5-flash", "minimal", "llm_gemini-2.5-flash", "SUCCESS"),
        _result_row("quests/ru/Boat.qm", "gemini-2.5-flash", "minimal", "llm_gemini-2.5-flash", "FAILURE"),
        _result_row("quests/Scout.qm", "gpt-5-mini", "planner", "planner_gpt-5-mini", "SUCCESS"),
    ]

    db_runs = [
        _db_run(
            1, "quests/ru/Boat.qm", "Boat", "llm_gemini-2.5-flash", "minimal", "gemini-2.5-flash", "SUCCESS",
            usage={"total_tokens": 900, "estimated_cost_usd": 0.003},
            diagnostics={"total_steps": 12, "repetition_rate": 0.10},
            progress={"current": 100.0},
        ),
        _db_run(
            2, "quests/ru/Boat.qm", "Boat", "llm_gemini-2.5-flash", "minimal", "gemini-2.5-flash", "FAILURE",
            usage={"total_tokens": 600, "estimated_cost_usd": None},
            diagnostics={"total_steps": 18, "repetition_rate": 0.30},
            progress={"current": 40.0},
        ),
        _db_run(
            3, "quests/Scout.qm", "Scout", "planner_gpt-5-mini", "planner", "gpt-5-mini", "SUCCESS",
            usage={"total_tokens": 1200, "estimated_cost_usd": 0.006},
            diagnostics={"total_steps": 9, "repetition_rate": 0.0},
            progress={"current": 100.0},
        ),
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
    assert boat_row["avg_progress"] == pytest.approx(70.0)

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
        "avg_progress": 100.0,
    }


def test_leaderboard_modes_come_from_treatment_components(tmp_path, monkeypatch):
    """Mode grouping reads declared components, never the harness name."""
    monkeypatch.chdir(tmp_path)
    benchmark_dir = Path("results/benchmarks/bench_modes")
    benchmark_dir.mkdir(parents=True, exist_ok=True)

    cases = {
        "minimal": "minimal_prompt",
        "reasoning_recent": "short_context_reasoning",
        "reasoning_full": "full_history_reasoning",
        "memo_compact": "compact_memory_memo",
        "hinted_compact": "prompt_hints",
        "tool_compact": "tools_compact_memory",
        "tool_hinted": "tools_hints_compact_memory",
        "programmatic_memory": "tools_programmatic_memory",
        "planner": "planner_loop",
        "backtracking": "backtracking_loop",
        "adaptive_reasoning": "adaptive_reasoning",
    }
    results = [_result_row("quests/Core.qm", "gpt-5-mini", harness, f"agent_{harness}") for harness in cases]
    (benchmark_dir / "benchmark_summary.json").write_text(
        json.dumps({"benchmark_id": "bench_modes", "agents": [], "results": results, "db_runs": []}),
        encoding="utf-8",
    )

    leaderboard = generate_leaderboard(
        [str(benchmark_dir)],
        "site/leaderboard.json",
        min_runs=0,
        public_model_ids=None,
    )

    assert {row["mode"] for row in leaderboard["results"]} == set(cases.values())


def test_leaderboard_marks_migrated_unknown_treatments(tmp_path, monkeypatch):
    """A migrated legacy record groups as unknown, not as a guessed mode."""
    monkeypatch.chdir(tmp_path)
    benchmark_dir = Path("results/benchmarks/bench_unknown")
    benchmark_dir.mkdir(parents=True, exist_ok=True)

    row = _result_row("quests/Core.qm", "gpt-5-mini", "minimal", "agent")
    row["treatment"] = {
        "harness": "unknown",
        "prompt": "unknown",
        "memory": "unknown",
        "tools": [],
        "loop": "unknown",
        "reasoning": "unknown",
        "signature": "t2_unknown",
    }
    (benchmark_dir / "benchmark_summary.json").write_text(
        json.dumps({"benchmark_id": "bench_unknown", "agents": [], "results": [row], "db_runs": []}),
        encoding="utf-8",
    )

    leaderboard = generate_leaderboard(
        [str(benchmark_dir)],
        "site/leaderboard.json",
        min_runs=0,
        public_model_ids=None,
    )

    assert leaderboard["results"][0]["mode"] == "unknown"


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
    # The site no longer carries a legacy mode-id alias map.
    assert "MODE_ALIASES" not in index_html

    leaderboard = json.loads((repo_root / "site/leaderboard.json").read_text(encoding="utf-8"))
    mode_labels = {mode["label"] for mode in leaderboard["modes"]}
    assert mode_labels == {
        "Minimal prompt",
        "Short-context reasoning",
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
            rows.append(_result_row(f"quests/{quest}.qm", model, "minimal", model))
    rows.append(_result_row("quests/Core.qm", "low-coverage", "minimal", "low-coverage"))
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


def test_generate_leaderboard_excludes_legacy_claude_cli_runs_from_public_slice(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    benchmark_dir = Path("results/benchmarks/bench_claude_cli")
    benchmark_dir.mkdir(parents=True, exist_ok=True)

    treatment = _treatment("memo_compact", "gpt-5-mini")
    rows = [
        {
            "quest": "quests/Core.qm",
            "model": "claude:claude-haiku-4-5-20251001",
            "harness": "memo_compact",
            "treatment": treatment,
            "agent_id": "legacy-claude-cli",
            "attempt": attempt,
            "outcome": "SUCCESS",
        }
        for attempt in range(10)
    ]
    rows.append(
        {
            "quest": "quests/Core.qm",
            "model": "anthropic:claude-haiku-4-5-20251001",
            "harness": "memo_compact",
            "treatment": treatment,
            "agent_id": "anthropic-api",
            "attempt": 1,
            "outcome": "SUCCESS",
        }
    )

    (benchmark_dir / "benchmark_summary.json").write_text(
        json.dumps({"benchmark_id": "bench_claude_cli", "agents": [], "results": rows, "db_runs": []}),
        encoding="utf-8",
    )

    leaderboard = generate_leaderboard(
        [str(benchmark_dir)],
        "site/leaderboard.json",
        min_runs=1,
        public_model_ids=["claude-haiku-4.5"],
    )

    assert [model["id"] for model in leaderboard["models"]] == ["claude-haiku-4.5"]
    assert len(leaderboard["results"]) == 1
    assert leaderboard["results"][0]["model"] == "claude-haiku-4.5"
    assert leaderboard["results"][0]["runs"] == 1


def test_generate_leaderboard_excludes_retired_exp4_variants(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    active_dir = Path("results/benchmarks/active")
    active_dir.mkdir(parents=True, exist_ok=True)
    retired_dir = Path("results/benchmarks/retired")
    retired_dir.mkdir(parents=True, exist_ok=True)

    active_row = _result_row("quests/Core.qm", "gpt-5-mini", "memo_compact", "active")
    retired_rows = [
        _result_row("quests/Core.qm", "gpt-5-mini", "compaction_no_memo", "retired-no-memo", "FAILURE"),
        _result_row("quests/Core.qm", "gpt-5-mini", "memo_extended", "retired-extended", "FAILURE"),
    ]

    (active_dir / "benchmark_summary.json").write_text(
        json.dumps({"benchmark_id": "active", "name": "active", "agents": [], "results": [active_row], "db_runs": []}),
        encoding="utf-8",
    )
    (retired_dir / "benchmark_summary.json").write_text(
        json.dumps(
            {
                "benchmark_id": "retired",
                "name": "exp4_compaction_no_memo",
                "agents": [],
                "results": retired_rows,
                "db_runs": [],
            }
        ),
        encoding="utf-8",
    )

    leaderboard = generate_leaderboard(
        [str(active_dir), str(retired_dir)],
        "site/leaderboard.json",
        min_runs=0,
        public_model_ids=None,
    )

    assert len(leaderboard["results"]) == 1
    assert leaderboard["results"][0]["mode"] == "compact_memory_memo"
    assert leaderboard["results"][0]["runs"] == 1


def test_generate_leaderboard_matches_db_runs_by_identifiers(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    benchmark_dir = Path("results/benchmarks/bench_match")
    benchmark_dir.mkdir(parents=True, exist_ok=True)

    results = [
        _result_row("quests/Alpha.qm", "gpt-5-mini", "minimal", "llm_gpt-5-mini"),
        _result_row("quests/Beta.qm", "gpt-5-mini", "minimal", "llm_gpt-5-mini"),
    ]
    db_runs = [
        _db_run(20, "quests/Beta.qm", "Beta", "llm_gpt-5-mini", "reasoning_full", "gpt-5-mini", "SUCCESS"),
        _db_run(10, "quests/Alpha.qm", "Alpha", "llm_gpt-5-mini", "memo_compact", "gpt-5-mini", "SUCCESS"),
    ]
    (benchmark_dir / "benchmark_summary.json").write_text(
        json.dumps({"benchmark_id": "bench_match", "agents": [], "results": results, "db_runs": db_runs}),
        encoding="utf-8",
    )

    # Usage/diagnostics fall back to a strict canonical run record when the DB row omits them.
    for run_id, quest_name, total_steps in [(10, "Alpha", 10), (20, "Beta", 20)]:
        path = Path("results/llm_gpt-5-mini") / quest_name / f"run_{run_id}" / "run_summary.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        db_run = next(row for row in db_runs if row["id"] == run_id)
        path.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "run": {"id": run_id, "agent_id": "llm_gpt-5-mini"},
                    "quest": {"file": f"quests/{quest_name}.qm", "name": quest_name},
                    "treatment": db_run["treatment"],
                    "lineage": None,
                    "terminal": {"outcome": "SUCCESS", "reward": 1.0, "snapshot": None},
                    "usage": {"total_tokens": total_steps},
                    "progress": {"current": 0.0, "maximum": 100.0, "scored": False},
                    "transcript_diagnostics": {"total_steps": total_steps},
                    "transitions": [],
                }
            ),
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
