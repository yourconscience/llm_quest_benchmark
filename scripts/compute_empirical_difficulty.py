#!/usr/bin/env python3
"""Compute empirical difficulty tiers from actual LLM success rates.

Queries metrics.db for per-quest success rates across all agents,
assigns tiers based on observed LLM performance (not human hardness),
and updates configs/quest_metadata.json.

Usage:
    uv run scripts/compute_empirical_difficulty.py [--db metrics.db] [--metadata configs/quest_metadata.json]
"""

import argparse
import json
import sqlite3
from pathlib import Path


JUNK_QUESTS = {"test_quest", "quest_1", "repeatable_quest", "repeatable", "nonexistent"}

# Tier boundaries based on LLM success rate
TIER_BOUNDARIES = {
    "trivial": 0.66,    # >66% success
    "medium": 0.10,     # 10-66% success
    "hard": 0.01,       # 1-10% success
    "impossible": 0.0,  # 0% success
}


def compute_tiers(db_path: Path) -> list[dict]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT
            quest_name,
            COUNT(*) as total_runs,
            SUM(CASE WHEN outcome='SUCCESS' THEN 1 ELSE 0 END) as successes,
            COUNT(DISTINCT agent_id) as agent_count,
            ROUND(100.0 * SUM(CASE WHEN outcome='SUCCESS' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_pct
        FROM runs
        WHERE quest_name NOT IN ({})
          AND outcome IS NOT NULL
          AND outcome != ''
        GROUP BY quest_name
        ORDER BY success_pct DESC
    """.format(",".join(f"'{q}'" for q in JUNK_QUESTS)))

    results = []
    for row in rows:
        rate = row["successes"] / row["total_runs"] if row["total_runs"] > 0 else 0
        if rate > TIER_BOUNDARIES["trivial"]:
            tier = "trivial"
        elif rate > TIER_BOUNDARIES["medium"]:
            tier = "medium"
        elif rate > TIER_BOUNDARIES["hard"]:
            tier = "hard"
        else:
            tier = "impossible"

        results.append({
            "quest_name": row["quest_name"],
            "total_runs": row["total_runs"],
            "successes": row["successes"],
            "success_rate": rate,
            "success_pct": row["success_pct"],
            "agent_count": row["agent_count"],
            "empirical_tier": tier,
        })

    conn.close()
    return results


def update_metadata(metadata_path: Path, tiers: list[dict]) -> int:
    if not metadata_path.exists():
        print(f"Warning: {metadata_path} not found, skipping metadata update")
        return 0

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    tier_lookup = {t["quest_name"]: t for t in tiers}

    updated = 0
    for quest_path, quest_meta in metadata.items():
        # Match by quest name (filename without extension and path)
        quest_name = Path(quest_path).stem
        # Strip _eng suffix for matching
        base_name = quest_name.removesuffix("_eng")

        tier_data = tier_lookup.get(quest_name) or tier_lookup.get(base_name)
        if tier_data:
            quest_meta["empirical_tier"] = tier_data["empirical_tier"]
            quest_meta["empirical_success_rate"] = tier_data["success_rate"]
            quest_meta["empirical_runs"] = tier_data["total_runs"]
            updated += 1

    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return updated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="metrics.db")
    parser.add_argument("--metadata", default="configs/quest_metadata.json")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Error: {db_path} not found")
        return

    tiers = compute_tiers(db_path)

    # Print summary table
    print(f"{'Quest':<25} {'Runs':>5} {'Success':>8} {'Rate':>7} {'Tier':<12}")
    print("-" * 65)

    tier_counts = {"trivial": 0, "medium": 0, "hard": 0, "impossible": 0}
    for t in tiers:
        tier_counts[t["empirical_tier"]] += 1
        print(f"{t['quest_name']:<25} {t['total_runs']:>5} {t['successes']:>8} {t['success_pct']:>6.1f}% {t['empirical_tier']:<12}")

    print("-" * 65)
    print(f"\nTier distribution:")
    for tier, count in tier_counts.items():
        print(f"  {tier}: {count} quests")

    # Update metadata
    metadata_path = Path(args.metadata)
    updated = update_metadata(metadata_path, tiers)
    print(f"\nUpdated {updated} entries in {metadata_path}")

    # Save full tier data
    output_path = Path("research/empirical_difficulty.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(tiers, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Full tier data written to {output_path}")


if __name__ == "__main__":
    main()
