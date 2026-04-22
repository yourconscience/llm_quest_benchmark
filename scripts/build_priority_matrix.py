#!/usr/bin/env python3
"""Build a priority matrix from failure classifications.

Reads failure_classifications.json, computes frequency x severity per failure mode
and per quest, outputs a markdown report.

Usage:
    uv run scripts/build_priority_matrix.py [--input research/failure_classifications.json] [--output research/priority_matrix.md]
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def build_matrix(classifications: list[dict]) -> dict:
    valid = [c for c in classifications if "error" not in c and c.get("failure_mode")]

    # Overall failure mode distribution
    mode_counts = Counter(c["failure_mode"] for c in valid)
    mode_severity = defaultdict(list)
    for c in valid:
        mode_severity[c["failure_mode"]].append(c.get("severity", 2))

    # Per-quest breakdown
    quest_modes = defaultdict(lambda: Counter())
    quest_severity = defaultdict(lambda: defaultdict(list))
    for c in valid:
        quest_modes[c["quest"]][c["failure_mode"]] += 1
        quest_severity[c["quest"]][c["failure_mode"]].append(c.get("severity", 2))

    # Per-agent breakdown
    agent_modes = defaultdict(lambda: Counter())
    for c in valid:
        agent = c.get("agent", "unknown")
        # Simplify agent name: extract model name
        if ":" in agent:
            parts = agent.split(":")
            agent = parts[-1].split("/")[-1] if "/" in parts[-1] else parts[-1]
        agent_modes[agent][c["failure_mode"]] += 1

    return {
        "total": len(valid),
        "mode_counts": dict(mode_counts),
        "mode_severity": {m: sum(s) / len(s) for m, s in mode_severity.items()},
        "quest_modes": {q: dict(c) for q, c in quest_modes.items()},
        "quest_severity": {q: {m: sum(s) / len(s) for m, s in modes.items()} for q, modes in quest_severity.items()},
        "agent_modes": {a: dict(c) for a, c in agent_modes.items()},
    }


def format_markdown(matrix: dict) -> str:
    lines = []
    lines.append("# Failure Priority Matrix")
    lines.append("")
    lines.append(f"**Total classified runs:** {matrix['total']}")
    lines.append("")

    # Overall distribution
    lines.append("## Failure Mode Distribution")
    lines.append("")
    lines.append("| Mode | Count | % | Avg Severity | Priority Score |")
    lines.append("|------|-------|---|-------------|----------------|")

    total = matrix["total"]
    priorities = {}
    for mode, count in sorted(matrix["mode_counts"].items(), key=lambda x: -x[1]):
        pct = 100 * count / total
        avg_sev = matrix["mode_severity"].get(mode, 2)
        priority = pct * avg_sev / 100  # normalized priority score
        priorities[mode] = priority
        lines.append(f"| {mode} | {count} | {pct:.1f}% | {avg_sev:.1f} | {priority:.2f} |")

    # Priority ranking
    lines.append("")
    lines.append("## Priority Ranking")
    lines.append("")
    lines.append("Priority = (frequency %) x (avg severity) / 100. Higher = more important to address.")
    lines.append("")
    for i, (mode, score) in enumerate(sorted(priorities.items(), key=lambda x: -x[1]), 1):
        lines.append(f"{i}. **{mode}** (priority {score:.2f})")

    # Per-quest heatmap
    lines.append("")
    lines.append("## Per-Quest Breakdown")
    lines.append("")
    all_modes = sorted(matrix["mode_counts"].keys())
    header = "| Quest | " + " | ".join(all_modes) + " | Dominant |"
    sep = "|-------|" + "|".join(["---"] * len(all_modes)) + "|----------|"
    lines.append(header)
    lines.append(sep)

    for quest in sorted(matrix["quest_modes"].keys()):
        modes = matrix["quest_modes"][quest]
        dominant = max(modes, key=modes.get) if modes else "?"
        cells = [str(modes.get(m, 0)) for m in all_modes]
        lines.append(f"| {quest} | " + " | ".join(cells) + f" | **{dominant}** |")

    # Per-agent breakdown
    lines.append("")
    lines.append("## Per-Agent Breakdown")
    lines.append("")
    header = "| Agent | " + " | ".join(all_modes) + " | Dominant |"
    lines.append(header)
    lines.append(sep)

    for agent in sorted(matrix["agent_modes"].keys()):
        modes = matrix["agent_modes"][agent]
        dominant = max(modes, key=modes.get) if modes else "?"
        cells = [str(modes.get(m, 0)) for m in all_modes]
        lines.append(f"| {agent} | " + " | ".join(cells) + f" | **{dominant}** |")

    # Key findings
    lines.append("")
    lines.append("## Key Findings")
    lines.append("")

    top_mode = max(matrix["mode_counts"], key=matrix["mode_counts"].get)
    top_count = matrix["mode_counts"][top_mode]
    top_pct = 100 * top_count / total
    lines.append(f"1. **{top_mode}** is the dominant failure mode ({top_pct:.0f}% of all failures)")

    # Quests where a single mode dominates (>80%)
    single_mode_quests = []
    for quest, modes in matrix["quest_modes"].items():
        quest_total = sum(modes.values())
        dominant = max(modes, key=modes.get)
        if modes[dominant] / quest_total > 0.8:
            single_mode_quests.append((quest, dominant, modes[dominant] / quest_total))

    if single_mode_quests:
        lines.append(f"2. **{len(single_mode_quests)} quests** have a single dominant failure mode (>80%):")
        for quest, mode, pct in sorted(single_mode_quests, key=lambda x: -x[2])[:10]:
            lines.append(f"   - {quest}: {mode} ({pct:.0%})")

    # High-severity quests
    high_sev = []
    for quest, modes in matrix["quest_severity"].items():
        avg = sum(modes.values()) / len(modes)
        if avg > 2.5:
            high_sev.append((quest, avg))
    if high_sev:
        lines.append(f"3. **High-severity quests** (avg severity > 2.5): {', '.join(q for q, _ in sorted(high_sev, key=lambda x: -x[1]))}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="research/failure_classifications.json")
    parser.add_argument("--output", default="research/priority_matrix.md")
    args = parser.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    classifications = data.get("classifications", [])

    print(f"Building priority matrix from {len(classifications)} classifications")

    matrix = build_matrix(classifications)
    md = format_markdown(matrix)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(md, encoding="utf-8")
    print(f"Written to {output_path}")

    # Also save raw matrix as JSON for programmatic use
    json_path = output_path.with_suffix(".json")
    json_path.write_text(json.dumps(matrix, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Raw matrix written to {json_path}")


if __name__ == "__main__":
    main()
