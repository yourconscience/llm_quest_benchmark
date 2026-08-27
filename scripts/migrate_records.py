#!/usr/bin/env python3
"""One-time migration of legacy pre-v2 records into schema v2.

The only legacy reader in the project. Lives outside the core package:
migration is a one-shot data-archaeology tool, not a runtime concern, and
the CLI surface stays minimal.

Usage:
    uv run scripts/migrate_records.py --source results/ --output results_v2/
    uv run scripts/migrate_records.py --source metrics.db --output metrics_v2.db

Accepts a legacy ``run_summary.json``, a tree of them, or a legacy SQLite
database (``runs`` + ``steps``). Migration never invents a missing action,
timestamp, parameter state, engine saving, or post-state; unknowable fields
are marked unavailable and block resume.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm_quest_benchmark.core.migration import migrate_records  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert legacy records into schema v2.")
    parser.add_argument("--source", required=True, help="Legacy run_summary.json, results tree, or SQLite database.")
    parser.add_argument("--output", required=True, help="Destination for the schema-v2 records.")
    args = parser.parse_args()

    try:
        report = migrate_records(args.source, args.output)
    except (FileNotFoundError, ValueError) as exc:
        log.error(f"Migration failed: {exc}")
        return 1
    except Exception:  # pragma: no cover - defensive
        log.exception("Error during migration")
        return 2

    print(f"Migrated {report.runs_migrated} runs ({report.kind}) to {report.output}")
    print(f"Transitions migrated: {report.transitions_migrated}")
    print(f"Resumable runs: {report.resumable_runs}")
    for skipped in report.skipped:
        print(f"Skipped {skipped}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
