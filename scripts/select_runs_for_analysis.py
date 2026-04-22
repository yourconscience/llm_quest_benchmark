#!/usr/bin/env python3
"""Select a stratified sample of runs for error analysis.

Rules:
- Exclude junk quests (test_quest, quest_1, repeatable*, nonexistent)
- Exclude ERROR outcome (infra failures, not agent failures)
- Include ALL runs from quests with <100 total runs
- For quests with >=100 runs, take up to 100 failures+timeouts:
  - Diverse agents (round-robin across distinct agent_ids)
  - Prefer runs with reasoning (has llm_decision.reasoning)
  - Prefer recent runs (higher run_id)
- Output: manifest JSON with list of run_summary.json paths

Usage:
    uv run scripts/select_runs_for_analysis.py [--results-dir results/] [--output research/analysis_manifest.json]
"""

import argparse
import json
import glob
import os
from collections import defaultdict
from pathlib import Path


JUNK_QUESTS = {"test_quest", "quest_1", "repeatable_quest", "repeatable", "nonexistent"}
ANALYSIS_OUTCOMES = {"FAILURE", "TIMEOUT"}
MAX_PER_QUEST = 50


def load_run(path: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def has_reasoning(run: dict) -> bool:
    for step in run.get("steps", []):
        r = (step.get("llm_decision") or {}).get("reasoning") or ""
        if r and "error" not in r.lower()[:20]:
            return True
    return False


def select_runs(results_dir: Path) -> list[dict]:
    all_files = sorted(glob.glob(str(results_dir / "**" / "run_summary.json"), recursive=True))
    print(f"Found {len(all_files)} run_summary.json files")

    by_quest: dict[str, list[dict]] = defaultdict(list)
    skipped_junk = skipped_outcome = skipped_error = 0

    for path in all_files:
        # Skip benchmark aggregate files
        if "/benchmarks/" in path:
            continue

        run = load_run(path)
        if run is None:
            continue

        quest = run.get("quest_name", "")
        if quest in JUNK_QUESTS:
            skipped_junk += 1
            continue

        outcome = run.get("outcome", "")
        if outcome not in ANALYSIS_OUTCOMES:
            skipped_outcome += 1
            continue

        if outcome == "ERROR":
            skipped_error += 1
            continue

        by_quest[quest].append({
            "path": path,
            "quest": quest,
            "agent": run.get("agent_id", ""),
            "outcome": outcome,
            "steps": len(run.get("steps", [])),
            "has_reasoning": has_reasoning(run),
            "run_id": run.get("run_id", 0),
        })

    print(f"Skipped: {skipped_junk} junk, {skipped_outcome} non-failure outcomes, {skipped_error} errors")
    print(f"Quests with failures: {len(by_quest)}")

    selected = []
    for quest, runs in sorted(by_quest.items()):
        total = len(runs)
        if total <= MAX_PER_QUEST:
            selected.extend(runs)
            print(f"  {quest}: {total} runs (all included)")
        else:
            # Stratified sampling: diverse agents, prefer reasoning, prefer recent
            runs_with_reasoning = [r for r in runs if r["has_reasoning"]]
            runs_without = [r for r in runs if not r["has_reasoning"]]

            # Sort each group by agent (for diversity) then by run_id desc (recent first)
            for group in [runs_with_reasoning, runs_without]:
                group.sort(key=lambda r: (r["agent"], -r["run_id"]))

            # Round-robin across agents from reasoning group first
            agents = sorted(set(r["agent"] for r in runs))
            agent_pools = defaultdict(list)
            for r in runs_with_reasoning:
                agent_pools[r["agent"]].append(r)
            for r in runs_without:
                agent_pools[r["agent"]].append(r)

            sample = []
            idx = {a: 0 for a in agents}
            while len(sample) < MAX_PER_QUEST:
                added = False
                for agent in agents:
                    pool = agent_pools[agent]
                    if idx[agent] < len(pool):
                        sample.append(pool[idx[agent]])
                        idx[agent] += 1
                        added = True
                        if len(sample) >= MAX_PER_QUEST:
                            break
                if not added:
                    break

            selected.extend(sample)
            agent_count = len(set(r["agent"] for r in sample))
            print(f"  {quest}: {total} -> {len(sample)} runs ({agent_count} agents)")

    print(f"\nTotal selected: {len(selected)} runs across {len(by_quest)} quests")
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", default="results", help="Path to results directory")
    parser.add_argument("--output", default="research/analysis_manifest.json", help="Output manifest path")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    if not results_dir.is_dir():
        print(f"Error: {results_dir} not found")
        return

    selected = select_runs(results_dir)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    manifest = {
        "total_runs": len(selected),
        "quests": len(set(r["quest"] for r in selected)),
        "agents": len(set(r["agent"] for r in selected)),
        "runs": [{"path": r["path"], "quest": r["quest"], "agent": r["agent"], "outcome": r["outcome"], "steps": r["steps"]} for r in selected],
    }
    output_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Manifest written to {output_path}")


if __name__ == "__main__":
    main()
