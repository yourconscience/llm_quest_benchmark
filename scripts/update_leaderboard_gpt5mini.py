#!/usr/bin/env python3
"""
Generate updated leaderboard entries for gpt-5.4-mini from the benchmark SQLite DB.

For each mode+quest combination, select exactly 3 canonical runs:
- Use the primary benchmark ID for that mode first (ordered by start_time)
- Fill remaining slots from other benchmark IDs if needed
- Exclude ERROR outcomes; only count SUCCESS/FAILURE/TIMEOUT

Run with: uv run python scripts/update_leaderboard_gpt5mini.py
"""

import json
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path

DB_PATH = Path("/Users/conscience/Workspace/llm_quest_benchmark/metrics.db")
LEADERBOARD_PATH = Path("/Users/conscience/Workspace/llm_quest_benchmark/site/leaderboard.json")

# All benchmark IDs that contain gpt-5.4-mini data for this campaign
ALL_BENCHMARK_IDS = [
    "CLI_benchmark_20260507_204025_38a962dc",
    "CLI_benchmark_20260508_074111_55ab74d3",
    "CLI_benchmark_20260508_144122_8d5d6af2",
    "CLI_benchmark_20260508_154409_32c8cb9d",
    "CLI_benchmark_20260508_164207_6aa38665",
    "CLI_benchmark_20260508_164759_8c30e7f2",
]

# Primary benchmark ID per mode (for tie-breaking / preference ordering)
# Modes 1-4 and 6-7 use the first benchmark; mode 5 (light_hints) uses the second
MODE_PRIMARY = {
    "minimal_prompt":              "CLI_benchmark_20260507_204025_38a962dc",
    "short_context_reasoning":     "CLI_benchmark_20260507_204025_38a962dc",
    "full_history_reasoning":      "CLI_benchmark_20260507_204025_38a962dc",
    "compact_memory_memo":         "CLI_benchmark_20260507_204025_38a962dc",
    "prompt_hints":                "CLI_benchmark_20260508_074111_55ab74d3",
    "tools_compact_memory":        "CLI_benchmark_20260507_204025_38a962dc",
    "tools_hints_compact_memory":  "CLI_benchmark_20260507_204025_38a962dc",
    "planner_loop":                "CLI_benchmark_20260507_204025_38a962dc",
}

# (action_template, memory_mode) -> mode_id
TEMPLATE_TO_MODE = {
    ("stub.jinja", "default"):                   "minimal_prompt",
    ("reasoning.jinja", "default"):              "short_context_reasoning",
    ("reasoning.jinja", "full_transcript"):      "full_history_reasoning",
    ("stateful_compact.jinja", "compaction"):    "compact_memory_memo",
    ("light_hints.jinja", "default"):            "prompt_hints",
    ("tool_augmented.jinja", "compaction"):      "tools_compact_memory",
    ("tool_augmented_hints.jinja", "compaction"): "tools_hints_compact_memory",
    ("planner.jinja", "default"):                "planner_loop",
}

VALID_OUTCOMES = {"SUCCESS", "FAILURE", "TIMEOUT"}
CANONICAL_RUNS = 3


def fetch_runs(conn: sqlite3.Connection) -> list[dict]:
    placeholders = ",".join("?" for _ in ALL_BENCHMARK_IDS)
    query = f"""
        SELECT
            id,
            quest_name,
            start_time,
            benchmark_id,
            outcome,
            agent_config
        FROM runs
        WHERE benchmark_id IN ({placeholders})
        ORDER BY start_time ASC
    """
    cursor = conn.execute(query, ALL_BENCHMARK_IDS)
    columns = [d[0] for d in cursor.description]
    rows = []
    for row in cursor.fetchall():
        r = dict(zip(columns, row))
        cfg = json.loads(r["agent_config"])
        r["action_template"] = cfg.get("action_template", "")
        r["memory_mode"] = cfg.get("memory_mode", "default")
        rows.append(r)
    return rows


def resolve_mode(action_template: str, memory_mode: str) -> str | None:
    return TEMPLATE_TO_MODE.get((action_template, memory_mode))


def select_canonical_runs(runs: list[dict]) -> list[dict]:
    """
    For each (mode, quest) group, pick exactly CANONICAL_RUNS runs.
    Preference: primary benchmark ID first (already sorted by start_time),
    then fill from other IDs.
    """
    # Group by (mode, quest)
    groups: dict[tuple, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in runs:
        mode = resolve_mode(r["action_template"], r["memory_mode"])
        if mode is None:
            continue
        if r["outcome"] not in VALID_OUTCOMES:
            continue
        quest = r["quest_name"]
        groups[(mode, quest)][r["benchmark_id"]].append(r)

    selected = []
    for (mode, quest), by_benchmark in sorted(groups.items()):
        primary = MODE_PRIMARY[mode]
        # Build ordered list: primary first, then others in deterministic order
        ordered: list[dict] = []
        for r in by_benchmark.get(primary, []):
            ordered.append(r)
        for bid, rlist in sorted(by_benchmark.items()):
            if bid == primary:
                continue
            ordered.extend(rlist)

        canonical = ordered[:CANONICAL_RUNS]
        selected.append((mode, quest, canonical))

    return selected


def compute_result(model: str, mode: str, quest: str, runs: list[dict]) -> dict:
    n = len(runs)
    successes = sum(1 for r in runs if r["outcome"] == "SUCCESS")
    return {
        "model": model,
        "mode": mode,
        "quest": quest,
        "runs": n,
        "success_rate": successes / n if n > 0 else 0.0,
        "avg_steps": 0,
        "avg_tokens": 0,
        "avg_cost_usd": 0,
        "repetition_rate": 0,
    }


def main():
    conn = sqlite3.connect(DB_PATH)
    all_runs = fetch_runs(conn)
    conn.close()

    print(f"Fetched {len(all_runs)} total runs from DB")

    canonical_groups = select_canonical_runs(all_runs)

    new_results = []
    for mode, quest, runs in canonical_groups:
        entry = compute_result("gpt-5.4-mini", mode, quest, runs)
        new_results.append(entry)

    # Report what we built
    from collections import Counter
    mode_counts = Counter(e["mode"] for e in new_results)
    print(f"\nBuilt {len(new_results)} result entries:")
    for mode, count in sorted(mode_counts.items()):
        successes = sum(1 for e in new_results if e["mode"] == mode and e["success_rate"] > 0)
        print(f"  {mode}: {count} quests")

    # Load existing leaderboard
    leaderboard = json.loads(LEADERBOARD_PATH.read_text())

    # Remove all existing gpt-5.4-mini entries
    before = len(leaderboard["results"])
    leaderboard["results"] = [
        r for r in leaderboard["results"] if r["model"] != "gpt-5.4-mini"
    ]
    after = len(leaderboard["results"])
    print(f"\nRemoved {before - after} existing gpt-5.4-mini entries")

    # Append new entries
    leaderboard["results"].extend(new_results)
    leaderboard["generated"] = datetime.utcnow().isoformat()

    LEADERBOARD_PATH.write_text(json.dumps(leaderboard, indent=2, ensure_ascii=False))
    print(f"Added {len(new_results)} new gpt-5.4-mini entries")
    print(f"Leaderboard written to {LEADERBOARD_PATH}")

    # Quick sanity print
    print("\nSample entries:")
    for e in new_results[:5]:
        print(f"  {e['mode']}/{e['quest']}: {e['runs']} runs, success={e['success_rate']:.2f}")


if __name__ == "__main__":
    main()
