#!/usr/bin/env python3
"""Replay existing runs to extract per-step location_ids.

Reads each run_summary.json, replays the recorded choice sequence through
QMPlayerEnv, and writes a location_trace.json alongside each run_summary.json.

The trace list is aligned with steps[]: trace[i] is the location_id when
step i was presented to the agent.

Usage:
    uv run scripts/replay_runs.py [--results-dir results/] [--limit N]

Note: The TS engine re-seeds its PRNG on each bridge startup, so replay of quests
with random branches diverges at the first stochastic choice. The trace is correct
up to that point and padded with None after. Fully deterministic quests replay 100%.
"""

import argparse
import json
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from llm_quest_benchmark.environments.qm import QMPlayerEnv  # noqa: E402


def _extract_choice(step: dict) -> str | None:
    """Extract 1-based choice key from llm_decision.choice dict."""
    decision = step.get("llm_decision") or {}
    choice = decision.get("choice")
    if not choice or not isinstance(choice, dict):
        return None
    return next(iter(choice))


def replay_run(summary_path: Path) -> dict:
    """Replay a single run and return the location trace.

    Returns a dict with keys:
        - run_id
        - quest_file
        - location_trace: list[str | None] aligned with steps[]
        - error: str | None  (set if replay failed partway through)
    """
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    run_id = data.get("run_id")
    quest_file = data.get("quest_file")
    steps = data.get("steps") or []

    result = {
        "run_id": run_id,
        "quest_file": quest_file,
        "location_trace": [],
        "error": None,
    }

    if not quest_file or not steps:
        result["error"] = "missing quest_file or steps"
        return result

    env = None
    try:
        env = QMPlayerEnv(quest_file)
        env.reset()
        result["location_trace"].append(env.state["location_id"])

        # Replay all but the last step (last step has no outgoing choice to take)
        for step in steps[:-1]:
            choice = _extract_choice(step)
            if choice is None:
                break
            env.step(choice)
            result["location_trace"].append(env.state["location_id"])

        # Pad to full length with None if replay stopped early
        while len(result["location_trace"]) < len(steps):
            result["location_trace"].append(None)
    except Exception as e:
        result["error"] = str(e)
        while len(result["location_trace"]) < len(steps):
            result["location_trace"].append(None)
    finally:
        if env is not None:
            env.close()

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", default="results", help="Path to results directory")
    parser.add_argument("--limit", type=int, default=0, help="Max runs to process (0 = all)")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    if not results_dir.is_dir():
        print(f"Error: results directory not found: {results_dir}", file=sys.stderr)
        sys.exit(1)

    summaries = sorted(results_dir.rglob("run_summary.json"))
    if args.limit:
        summaries = summaries[: args.limit]

    print(f"Replaying {len(summaries)} runs from {results_dir}")

    success = failed = skipped = 0
    for path in summaries:
        trace_path = path.parent / "location_trace.json"
        if trace_path.exists():
            skipped += 1
            continue

        print(f"  {path.relative_to(results_dir)}", end=" ... ", flush=True)
        trace = replay_run(path)

        tmp = trace_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(trace_path)

        if trace["error"]:
            print(f"PARTIAL ({trace['error'][:60]})")
            failed += 1
        else:
            covered = sum(1 for x in trace["location_trace"] if x is not None)
            print(f"OK ({covered}/{len(trace['location_trace'])} steps)")
            success += 1

    print(f"\nDone: {success} ok, {failed} partial/failed, {skipped} skipped (trace exists)")


if __name__ == "__main__":
    main()
