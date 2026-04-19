#!/usr/bin/env python3
"""Backfill estimated_cost_usd for existing run_summary.json files.

Token counts (prompt_tokens, completion_tokens) are already saved per run.
This script applies the current pricing table to compute costs retroactively
for runs where estimated_cost_usd is null.

Usage:
    uv run scripts/backfill_costs.py [--dry-run] [--results-dir results/]
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure repo root is on the path so we can import the benchmark package.
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from llm_quest_benchmark.llm.client import _estimate_cost_usd, parse_model_name  # noqa: E402


_AGENT_ID_PREFIXES = ("llm_", "planner_", "tool_")


def _model_name_from_agent_id(agent_id: str) -> str | None:
    for prefix in _AGENT_ID_PREFIXES:
        if agent_id.startswith(prefix):
            return agent_id[len(prefix):]
    return None


def backfill(results_dir: Path, dry_run: bool) -> None:
    summaries = list(results_dir.rglob("run_summary.json"))
    print(f"Found {len(summaries)} run_summary.json files under {results_dir}")

    updated = skipped_has_cost = skipped_no_tokens = skipped_no_model = skipped_no_price = 0

    for path in sorted(summaries):
        data = json.loads(path.read_text(encoding="utf-8"))
        usage = data.get("usage") or {}

        if usage.get("estimated_cost_usd") is not None:
            skipped_has_cost += 1
            continue

        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        if prompt_tokens == 0 and completion_tokens == 0:
            skipped_no_tokens += 1
            continue

        agent_id = data.get("agent_id") or ""
        model_name = _model_name_from_agent_id(agent_id)
        if not model_name:
            skipped_no_model += 1
            print(f"  SKIP (no model): {path.relative_to(results_dir)}")
            continue

        try:
            spec = parse_model_name(model_name)
        except (NotImplementedError, Exception):
            skipped_no_model += 1
            print(f"  SKIP (unparseable model '{model_name}'): {path.relative_to(results_dir)}")
            continue

        cost = _estimate_cost_usd(spec.provider, spec.model_id, prompt_tokens, completion_tokens)
        if cost is None:
            skipped_no_price += 1
            print(f"  SKIP (no price for {spec.provider}:{spec.model_id}): {path.relative_to(results_dir)}")
            continue

        total_steps = data.get("metrics", {}).get("total_steps") or 1
        print(
            f"  {'[DRY]' if dry_run else 'UPDATE'} {path.relative_to(results_dir)}"
            f"  {spec.provider}:{spec.model_id}"
            f"  {prompt_tokens}p+{completion_tokens}c tokens"
            f"  -> ${cost:.6f}"
        )

        if not dry_run:
            data["usage"]["estimated_cost_usd"] = round(cost, 8)
            data["usage"]["priced_steps"] = int(total_steps)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        updated += 1

    print()
    print(f"Results: {updated} {'would be ' if dry_run else ''}updated, "
          f"{skipped_has_cost} already had cost, "
          f"{skipped_no_tokens} had no tokens, "
          f"{skipped_no_model} had unknown model, "
          f"{skipped_no_price} had no price entry.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print what would change without writing files")
    parser.add_argument("--results-dir", default="results", help="Path to results directory (default: results/)")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    if not results_dir.is_dir():
        print(f"Error: results directory not found: {results_dir}", file=sys.stderr)
        sys.exit(1)

    backfill(results_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
