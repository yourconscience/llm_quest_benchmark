#!/usr/bin/env python3
"""Build paper-facing source data from the published leaderboard and tier configs."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
LEADERBOARD_PATH = ROOT / "site" / "leaderboard.json"
TIER_CONFIGS = {
    "easy": ROOT / "configs" / "benchmarks" / "tiered" / "tiered_easy_core_v1.yaml",
    "medium": ROOT / "configs" / "benchmarks" / "tiered" / "tiered_medium_core_v1.yaml",
    "hard": ROOT / "configs" / "benchmarks" / "tiered" / "tiered_hard_core_v1.yaml",
}
PAPER_DIR = ROOT / "paper"
DATA_DIR = PAPER_DIR / "data"
TABLE_DIR = PAPER_DIR / "tables"

MODE_ORDER = ["stub", "reasoning", "light_hints", "planner", "tool_augmented"]
MODE_LABELS = {
    "stub": "Baseline (A)",
    "reasoning": "Prompted (B)",
    "light_hints": "Knowledge (C)",
    "planner": "Planner (D)",
    "tool_augmented": "Tool-augmented (E)",
}
TIER_ORDER = ["easy", "medium", "hard"]
TIER_LABELS = {"easy": "Easy", "medium": "Medium", "hard": "Hard"}


@dataclass(frozen=True)
class Aggregate:
    runs: int
    success_rate: float
    quests: int
    models: int


def tex_escape(value: str) -> str:
    return (
        value.replace("\\", r"\textbackslash{}")
        .replace("&", r"\&")
        .replace("%", r"\%")
        .replace("_", r"\_")
    )


def format_pct(rate: float) -> str:
    return f"{rate * 100:.1f}\\%"


def load_leaderboard() -> dict[str, Any]:
    return json.loads(LEADERBOARD_PATH.read_text(encoding="utf-8"))


def load_tiers() -> dict[str, list[str]]:
    tiers: dict[str, list[str]] = {}
    for tier, path in TIER_CONFIGS.items():
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        quests = [Path(quest_path).stem for quest_path in payload.get("quests", [])]
        tiers[tier] = quests
    return tiers


def aggregate(rows: list[dict[str, Any]]) -> Aggregate:
    runs = sum(int(row["runs"]) for row in rows)
    weighted_success = sum(float(row["success_rate"]) * int(row["runs"]) for row in rows)
    quests = len({str(row["quest"]) for row in rows})
    models = len({str(row["model"]) for row in rows})
    return Aggregate(
        runs=runs,
        success_rate=(weighted_success / runs) if runs else 0.0,
        quests=quests,
        models=models,
    )


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_tables(
    leaderboard: dict[str, Any],
    tiers: dict[str, list[str]],
    tier_rows: list[dict[str, Any]],
    mode_by_tier_rows: list[dict[str, Any]],
    model_rows: list[dict[str, Any]],
) -> None:
    tier_summary_lines = [
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        r"Tier & Quests & Runs & Weighted success \\",
        r"\midrule",
    ]
    for row in tier_rows:
        tier_summary_lines.append(
            f"{tex_escape(row['tier_label'])} & {row['quest_count']} & {row['runs']} & {format_pct(row['success_rate'])} \\\\"
        )
    tier_summary_lines.extend([r"\bottomrule", r"\end{tabular}"])
    (TABLE_DIR / "tier_summary.tex").write_text("\n".join(tier_summary_lines) + "\n", encoding="utf-8")

    quest_tiers_lines = [
        r"\begin{tabular}{lp{0.72\linewidth}}",
        r"\toprule",
        r"Tier & Quest IDs \\",
        r"\midrule",
    ]
    for tier in TIER_ORDER:
        joined = ", ".join(tex_escape(quest) for quest in tiers[tier])
        quest_tiers_lines.append(f"{tex_escape(TIER_LABELS[tier])} & {joined} \\\\")
    quest_tiers_lines.extend([r"\bottomrule", r"\end{tabular}"])
    (TABLE_DIR / "quest_tiers.tex").write_text("\n".join(quest_tiers_lines) + "\n", encoding="utf-8")

    mode_lines = [
        r"\begin{tabular}{lccc}",
        r"\toprule",
        r"Mode & Easy & Medium & Hard \\",
        r"\midrule",
    ]
    mode_lookup = {(row["mode"], row["tier"]): row for row in mode_by_tier_rows}
    for mode in MODE_ORDER:
        cells = []
        for tier in TIER_ORDER:
            row = mode_lookup.get((mode, tier))
            if row is None:
                cells.append("n/a")
            else:
                cells.append(f"{format_pct(row['success_rate'])} ({row['runs']})")
        mode_lines.append(f"{tex_escape(MODE_LABELS[mode])} & " + " & ".join(cells) + r" \\")
    mode_lines.extend([r"\bottomrule", r"\end{tabular}"])
    (TABLE_DIR / "mode_by_tier.tex").write_text("\n".join(mode_lines) + "\n", encoding="utf-8")

    model_lines = [
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        r"Model & Runs & Weighted success & Covered quests \\",
        r"\midrule",
    ]
    for row in model_rows:
        model_lines.append(
            f"{tex_escape(row['label'])} & {row['runs']} & {format_pct(row['success_rate'])} & {row['quests']} \\\\"
        )
    model_lines.extend([r"\bottomrule", r"\end{tabular}"])
    (TABLE_DIR / "model_summary.tex").write_text("\n".join(model_lines) + "\n", encoding="utf-8")

    scope_note = {
        "leaderboard_generated": leaderboard.get("generated"),
        "paper_data_generated": datetime.now(UTC).isoformat(timespec="seconds"),
        "note": "All paper tables are descriptive summaries of the published six-model leaderboard slice.",
    }
    (DATA_DIR / "build_metadata.json").write_text(json.dumps(scope_note, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)

    leaderboard = load_leaderboard()
    tiers = load_tiers()
    all_quests = {quest["id"] for quest in leaderboard["quests"]}
    missing = sorted({quest for quests in tiers.values() for quest in quests if quest not in all_quests})
    if missing:
        raise SystemExit(f"Tier configs reference quests not present in leaderboard.json: {missing}")

    tier_map = {quest: tier for tier, quests in tiers.items() for quest in quests}
    model_labels = {model["id"]: model["label"] for model in leaderboard["models"]}
    rows = list(leaderboard["results"])

    tier_rows: list[dict[str, Any]] = []
    for tier in TIER_ORDER:
        subset = [row for row in rows if tier_map.get(str(row["quest"])) == tier]
        agg = aggregate(subset)
        tier_rows.append(
            {
                "tier": tier,
                "tier_label": TIER_LABELS[tier],
                "quest_count": len(tiers[tier]),
                "quests": ",".join(tiers[tier]),
                "runs": agg.runs,
                "success_rate": round(agg.success_rate, 6),
                "models": agg.models,
            }
        )

    mode_by_tier_rows: list[dict[str, Any]] = []
    for tier in TIER_ORDER:
        for mode in MODE_ORDER:
            subset = [row for row in rows if tier_map.get(str(row["quest"])) == tier and str(row["mode"]) == mode]
            if not subset:
                continue
            agg = aggregate(subset)
            mode_by_tier_rows.append(
                {
                    "tier": tier,
                    "tier_label": TIER_LABELS[tier],
                    "mode": mode,
                    "mode_label": MODE_LABELS[mode],
                    "runs": agg.runs,
                    "success_rate": round(agg.success_rate, 6),
                    "quests": agg.quests,
                    "models": agg.models,
                    "rows": len(subset),
                }
            )

    model_rows: list[dict[str, Any]] = []
    for model_id in sorted(model_labels):
        subset = [row for row in rows if str(row["model"]) == model_id]
        agg = aggregate(subset)
        model_rows.append(
            {
                "model": model_id,
                "label": model_labels[model_id],
                "runs": agg.runs,
                "success_rate": round(agg.success_rate, 6),
                "quests": agg.quests,
                "modes": len({str(row["mode"]) for row in subset}),
            }
        )
    model_rows.sort(key=lambda row: (-row["success_rate"], -row["runs"], row["label"]))

    quest_rows: list[dict[str, Any]] = []
    for quest in sorted(all_quests):
        subset = [row for row in rows if str(row["quest"]) == quest]
        agg = aggregate(subset)
        quest_rows.append(
            {
                "quest": quest,
                "tier": tier_map[quest],
                "runs": agg.runs,
                "success_rate": round(agg.success_rate, 6),
                "modes": len({str(row["mode"]) for row in subset}),
                "models": agg.models,
            }
        )
    quest_rows.sort(key=lambda row: (TIER_ORDER.index(row["tier"]), -row["success_rate"], row["quest"]))

    mode_overall_rows: list[dict[str, Any]] = []
    for mode in MODE_ORDER:
        subset = [row for row in rows if str(row["mode"]) == mode]
        if not subset:
            continue
        agg = aggregate(subset)
        mode_overall_rows.append(
            {
                "mode": mode,
                "mode_label": MODE_LABELS[mode],
                "runs": agg.runs,
                "success_rate": round(agg.success_rate, 6),
                "quests": agg.quests,
                "models": agg.models,
                "rows": len(subset),
            }
        )

    summary = {
        "source": str(LEADERBOARD_PATH.relative_to(ROOT)),
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "leaderboard_generated_at": leaderboard.get("generated"),
        "total_runs": sum(int(row["runs"]) for row in rows),
        "total_rows": len(rows),
        "models": leaderboard["models"],
        "modes": leaderboard["modes"],
        "tiers": tiers,
    }

    (DATA_DIR / "public_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_csv(DATA_DIR / "tier_summary.csv", list(tier_rows[0].keys()), tier_rows)
    write_csv(DATA_DIR / "mode_by_tier.csv", list(mode_by_tier_rows[0].keys()), mode_by_tier_rows)
    write_csv(DATA_DIR / "model_summary.csv", list(model_rows[0].keys()), model_rows)
    write_csv(DATA_DIR / "quest_summary.csv", list(quest_rows[0].keys()), quest_rows)
    write_csv(DATA_DIR / "mode_overall.csv", list(mode_overall_rows[0].keys()), mode_overall_rows)
    build_tables(leaderboard, tiers, tier_rows, mode_by_tier_rows, model_rows)

    print(f"Wrote paper data to {DATA_DIR.relative_to(ROOT)} and tables to {TABLE_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
