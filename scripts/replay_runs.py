#!/usr/bin/env python3
"""Verify schema-v2 run records by replaying them against the real engine.

Each run_summary.json is replayed transition by transition: recorded choose
timestamps and restore actions are re-executed and every resulting snapshot
digest is compared with the record. A replay_report.json is written alongside
each run_summary.json.

Legacy records are not accepted here. Convert them first with:
    llm-quest migrate-records --source <path> --output <path>

Usage:
    uv run scripts/replay_runs.py [--results-dir results/] [--limit N] [--force]
"""

import argparse
import json
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from llm_quest_benchmark.core.replay import ReplayError, replay_record, verify_environment  # noqa: E402
from llm_quest_benchmark.environments.qm import QMPlayerEnv  # noqa: E402
from llm_quest_benchmark.schemas.records import load_run_record  # noqa: E402


def replay_run(summary_path: Path) -> dict:
    """Replay one recorded run and return its verification report."""
    result = {
        "run_id": None,
        "quest_file": None,
        "verified_transitions": 0,
        "total_transitions": 0,
        "location_trace": [],
        "status": "failed",
        "error": None,
    }

    try:
        record = load_run_record(str(summary_path))
    except (ValueError, OSError) as exc:
        result["error"] = str(exc)
        return result

    result["run_id"] = record.run_id
    result["quest_file"] = record.quest_file
    result["total_transitions"] = len(record.transitions)
    # The recorded trace needs no replay: each transition carries its own state.
    result["location_trace"] = [t.before.location_id for t in record.transitions]
    if record.transitions:
        result["location_trace"].append(record.transitions[-1].after.location_id)

    if not record.transitions:
        result["status"] = "skipped"
        result["error"] = "record has no transitions"
        return result

    env = None
    try:
        verify_environment(record, record.quest_file)
        env = QMPlayerEnv(record.quest_file, language=record.quest_language)
        replay = replay_record(env, record)
        result["verified_transitions"] = replay.verified_transitions
        result["status"] = "verified"
    except ReplayError as exc:
        result["error"] = str(exc)
    except Exception as exc:  # noqa: BLE001 - report engine/setup failures verbatim
        result["error"] = str(exc)
    finally:
        if env is not None:
            env.close()

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", default="results", help="Path to results directory")
    parser.add_argument("--limit", type=int, default=0, help="Max runs to process (0 = all)")
    parser.add_argument("--force", action="store_true", help="Re-verify runs that already have a report")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    if not results_dir.is_dir():
        print(f"Error: results directory not found: {results_dir}", file=sys.stderr)
        sys.exit(1)

    summaries = sorted(results_dir.rglob("run_summary.json"))
    if args.limit:
        summaries = summaries[: args.limit]

    print(f"Replaying {len(summaries)} runs from {results_dir}")

    verified = failed = skipped = 0
    for path in summaries:
        report_path = path.parent / "replay_report.json"
        if report_path.exists() and not args.force:
            skipped += 1
            continue

        print(f"  {path.relative_to(results_dir)}", end=" ... ", flush=True)
        report = replay_run(path)

        tmp = report_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(report_path)

        if report["status"] == "verified":
            print(f"OK ({report['verified_transitions']}/{report['total_transitions']} transitions)")
            verified += 1
        elif report["status"] == "skipped":
            print(f"SKIPPED ({report['error']})")
            skipped += 1
        else:
            print(f"FAILED ({str(report['error'])[:80]})")
            failed += 1

    print(f"\nDone: {verified} verified, {failed} failed, {skipped} skipped")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
