#!/usr/bin/env python3
"""Build per-quest cohort data JSON files for the Play feature.

Reads metrics.db and writes site/play/{quest_name}.json for each target quest
with per-location choice distributions from AI model runs.

Usage:
    uv run python scripts/build_cohort_data.py
"""

import json
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from llm_quest_benchmark.core.quest_lang import EN_TO_RU_QUEST_MAP

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = REPO_ROOT / "metrics.db"
OUT_DIR = REPO_ROOT / "site" / "play"

TARGET_QUESTS = [
    "Banket_eng",
    "Badday_eng",
    "Pizza_eng",
    "Borzukhan_eng",
    "Ski_eng",
    "Election_eng",
    "Robots_eng",
    "Leonardo_eng",
    "Depth_eng",
    "Edelweiss_eng",
    "Ministry_eng",
    "Foncers_eng",
    "Driver_eng",
    "Codebox_eng",
    "Pilot_eng",
    "Disk_eng",
    "Sortirovka1_eng",
    "Shashki_eng",
    "Player_eng",
]

QUEST_METADATA: dict[str, dict] = {
    "Disk_eng": {
        "title": "Disk",
        "difficulty": "easy",
        "description": "Answer riddles from a malfunctioning ship computer.",
        "stepsRange": "6-9",
    },
    "Pizza_eng": {
        "title": "Pizza Delivery",
        "difficulty": "medium",
        "description": "Deliver a pizza across a hostile space station.",
        "stepsRange": "15-30",
    },
    "Badday_eng": {
        "title": "Bad Day",
        "difficulty": "hard",
        "description": "Survive a day when everything goes wrong.",
        "stepsRange": "20-40",
    },
    "Banket_eng": {
        "title": "Banquet",
        "difficulty": "medium",
        "description": "Navigate the politics of an interstellar banquet.",
        "stepsRange": "15-25",
    },
    "Borzukhan_eng": {
        "title": "Borzukhan",
        "difficulty": "hard",
        "description": "Infiltrate a fortified enemy base.",
        "stepsRange": "20-40",
    },
    "Ski_eng": {
        "title": "Ski Resort",
        "difficulty": "medium",
        "description": "Manage a ski resort on an alien planet.",
        "stepsRange": "15-25",
    },
    "Election_eng": {
        "title": "Election",
        "difficulty": "hard",
        "description": "Win a planetary election campaign.",
        "stepsRange": "25-50",
    },
    "Robots_eng": {
        "title": "Robots",
        "difficulty": "hard",
        "description": "Survive a robot uprising on a space station.",
        "stepsRange": "20-40",
    },
    "Leonardo_eng": {
        "title": "Leonardo",
        "difficulty": "hard",
        "description": "Solve mysteries in a Renaissance-themed quest.",
        "stepsRange": "20-40",
    },
    "Depth_eng": {
        "title": "Depth",
        "difficulty": "medium",
        "description": "Explore the depths of an underwater facility.",
        "stepsRange": "15-30",
    },
    "Edelweiss_eng": {
        "title": "Edelweiss",
        "difficulty": "medium",
        "description": "Navigate a mountain expedition gone wrong.",
        "stepsRange": "15-30",
    },
    "Ministry_eng": {
        "title": "Ministry",
        "difficulty": "hard",
        "description": "Navigate bureaucratic intrigue at a space ministry.",
        "stepsRange": "20-35",
    },
    "Foncers_eng": {
        "title": "Foncers",
        "difficulty": "medium",
        "description": "Compete in an underground racing league.",
        "stepsRange": "10-20",
    },
    "Driver_eng": {
        "title": "Driver",
        "difficulty": "hard",
        "description": "Complete a dangerous cargo delivery run.",
        "stepsRange": "25-50",
    },
    "Codebox_eng": {
        "title": "Code Box",
        "difficulty": "easy",
        "description": "Crack codes and solve puzzles.",
        "stepsRange": "5-15",
    },
    "Pilot_eng": {
        "title": "Pilot",
        "difficulty": "medium",
        "description": "Pass the pilot certification exam.",
        "stepsRange": "10-20",
    },
    "Sortirovka1_eng": {
        "title": "Sorting",
        "difficulty": "easy",
        "description": "Sort items in a warehouse puzzle.",
        "stepsRange": "5-10",
    },
    "Shashki_eng": {
        "title": "Checkers",
        "difficulty": "easy",
        "description": "Play a game of space checkers.",
        "stepsRange": "5-10",
    },
    "Player_eng": {
        "title": "Player",
        "difficulty": "easy",
        "description": "A simple introductory quest.",
        "stepsRange": "5-10",
    },
}

EXCLUDE_PATTERNS = ["random", "test", "planner", "tool"]

MIN_FAMILY_STEPS = 5


def classify_agent(agent_id: str) -> str:
    """Return model family string for a given agent_id."""
    a = agent_id.lower()
    # Claude (various prefix forms)
    if (
        "anthropic/claude" in a
        or "llm_anthropic:claude" in a
        or a.startswith("claude:claude")
        or "llm_claude:claude" in a
        or a.startswith("llm_claude-exec")
    ):
        return "claude"
    # Gemini (various prefix forms)
    if (
        "google/gemini" in a
        or "llm_openrouter:google/gemini" in a
        or "google:gemini" in a
        or a.startswith("llm_gemini")
    ):
        return "gemini"
    # OpenAI GPT
    if "openai/gpt" in a or "llm_openrouter:openai/gpt" in a or "openai:gpt" in a:
        return "openai"
    # DeepSeek
    if "deepseek/" in a or "deepseek:" in a:
        return "deepseek"
    # Qwen
    if "qwen/" in a or "qwen:" in a or ":qwen" in a:
        return "qwen"
    # Mistral
    if "mistralai/" in a or "mistral" in a:
        return "mistral"
    # LLaMA / Meta
    if "meta-llama/" in a or "llama" in a:
        return "llama"
    return "other"


def is_excluded(agent_id: str) -> bool:
    a = agent_id.lower()
    return any(pat in a for pat in EXCLUDE_PATTERNS)


_CYRILLIC_RE = re.compile(r"[Ѐ-ӿ]")


def has_cyrillic(text: str) -> bool:
    return bool(_CYRILLIC_RE.search(text))


def build_quest_data(conn: sqlite3.Connection, quest_name: str) -> dict:
    cursor = conn.cursor()

    # Fetch all runs for this quest (excluding filtered agent types, all outcomes)
    cursor.execute(
        """
        SELECT r.id, r.agent_id, r.outcome
        FROM runs r
        WHERE r.quest_name = ?
        """,
        (quest_name,),
    )
    all_runs = cursor.fetchall()

    # Filter runs
    runs = {}  # run_id -> (agent_id, outcome)
    unrecognized = set()
    for run_id, agent_id, outcome in all_runs:
        if is_excluded(agent_id):
            continue
        family = classify_agent(agent_id)
        if family == "other":
            unrecognized.add(agent_id)
        runs[run_id] = (agent_id, outcome, family)

    if unrecognized:
        for aid in sorted(unrecognized):
            print(f"  [WARN] unrecognized agent_id: {aid}", file=sys.stderr)

    total_runs = len(runs)
    success_runs = sum(1 for _, (_, outcome, _) in runs.items() if outcome == "SUCCESS")
    win_rate = success_runs / total_runs if total_runs > 0 else 0.0

    if not runs:
        return {
            "quest": quest_name,
            "generated": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_runs": 0,
            "win_rate": 0.0,
            "model_families": [],
            "locations": {},
        }

    run_ids = list(runs.keys())
    # Fetch steps for all relevant runs
    placeholders = ",".join("?" * len(run_ids))
    cursor.execute(
        f"""
        SELECT s.run_id, s.location_id, s.observation, s.choices, s.action
        FROM steps s
        WHERE s.run_id IN ({placeholders})
        ORDER BY s.run_id, s.step
        """,
        run_ids,
    )
    rows = cursor.fetchall()

    # Per-location: observation_preview, per-choice per-family counts
    # Structure: loc_data[loc_id]["obs"] = str
    #            loc_data[loc_id]["choices"][norm_text]["text"] = original text
    #            loc_data[loc_id]["choices"][norm_text]["counts"][family] = int
    loc_data: dict[str, dict] = {}

    # Track total steps per family (across all locations) for filtering
    family_total_steps: dict[str, int] = defaultdict(int)

    for run_id, location_id, observation, choices_json, action in rows:
        # Skip terminal/non-numeric actions
        if not str(action).strip().isdigit():
            continue

        action_idx = int(action) - 1  # convert 1-based to 0-based

        try:
            choices = json.loads(choices_json)
        except (json.JSONDecodeError, TypeError):
            continue

        if action_idx < 0 or action_idx >= len(choices):
            continue

        chosen = choices[action_idx]
        chosen_text = chosen.get("text", "")
        if has_cyrillic(chosen_text):
            continue
        norm_text = re.sub(r"<[^>]+>", "", chosen_text).strip().lower()

        _, _, family = runs[run_id]

        loc_id = str(location_id)
        if loc_id not in loc_data:
            loc_data[loc_id] = {
                "obs": (observation or "")[:80],
                "choices": {},
                "total": 0,
            }

        loc = loc_data[loc_id]
        loc["total"] += 1

        if norm_text not in loc["choices"]:
            loc["choices"][norm_text] = {
                "text": chosen_text,
                "counts": defaultdict(int),
            }

        loc["choices"][norm_text]["counts"][family] += 1
        family_total_steps[family] += 1

    # Determine which families have enough data
    included_families = sorted(fam for fam, count in family_total_steps.items() if count >= MIN_FAMILY_STEPS)

    # Build output locations dict
    output_locations: dict[str, dict] = {}
    for loc_id, loc in loc_data.items():
        total_at_loc = loc["total"]
        if total_at_loc == 0:
            continue

        out_choices: dict[str, dict] = {}
        for norm_text, choice_info in loc["choices"].items():
            counts = choice_info["counts"]
            n_total = sum(counts.values())

            dist: dict[str, float] = {"all": round(n_total / total_at_loc, 4)}
            n_by_family: dict[str, int] = {}

            for fam in included_families:
                if fam in counts:
                    dist[fam] = round(counts[fam] / total_at_loc, 4)
                    n_by_family[fam] = counts[fam]

            out_choices[norm_text] = {
                "text": choice_info["text"],
                "n": n_total,
                "dist": dist,
                "n_by_family": n_by_family,
            }

        output_locations[loc_id] = {
            "observation_preview": loc["obs"],
            "n": total_at_loc,
            "choices": out_choices,
        }

    return {
        "quest": quest_name,
        "generated": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_runs": total_runs,
        "win_rate": round(win_rate, 4),
        "model_families": included_families,
        "locations": output_locations,
    }


def main() -> None:
    if not DB_PATH.exists():
        print(f"Error: metrics.db not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    try:
        for quest_name in TARGET_QUESTS:
            print(f"Processing {quest_name}...")
            data = build_quest_data(conn, quest_name)

            out_path = OUT_DIR / f"{quest_name}.json"
            out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

            locs = data["locations"]
            n_locs = len(locs)
            n_locs_10plus = sum(1 for loc in locs.values() if loc["n"] >= 10)
            families_str = ", ".join(data["model_families"]) or "(none)"

            print(
                f"  {quest_name}: {data['total_runs']} runs, "
                f"win_rate={data['win_rate']:.1%}, "
                f"{n_locs} locations ({n_locs_10plus} with 10+ coverage), "
                f"families: [{families_str}]"
            )
            print(f"  -> {out_path}")
    finally:
        conn.close()

    # Build quest-index.json from generated cohort files. RU quest cards reuse
    # canonical EN metrics so the language toggle presents the same recorded AI
    # data end to end while loading localized quest text.
    print("\nBuilding quest-index.json...")
    index_quests = []
    for quest_name in TARGET_QUESTS:
        cohort_path = OUT_DIR / f"{quest_name}.json"
        if not cohort_path.exists():
            print(f"  [WARN] missing cohort file for {quest_name}, skipping", file=sys.stderr)
            continue
        cohort = json.loads(cohort_path.read_text(encoding="utf-8"))
        meta = QUEST_METADATA.get(quest_name, {})
        quest_entry = {
            "id": quest_name,
            "lang": "en",
            "canonical_id": quest_name,
            "title": meta.get("title", quest_name),
            "difficulty": meta.get("difficulty", "unknown"),
            "description": meta.get("description", ""),
            "stepsRange": meta.get("stepsRange", ""),
            "win_rate": cohort.get("win_rate", 0.0),
            "total_runs": cohort.get("total_runs", 0),
        }
        index_quests.append(quest_entry)

        ru_quest_id = EN_TO_RU_QUEST_MAP.get(quest_name)
        if ru_quest_id:
            index_quests.append(
                {
                    **quest_entry,
                    "id": ru_quest_id,
                    "lang": "ru",
                    "canonical_id": quest_name,
                }
            )

    index_path = OUT_DIR / "quest-index.json"
    index_path.write_text(
        json.dumps({"quests": index_quests}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  -> {index_path} ({len(index_quests)} quests)")


if __name__ == "__main__":
    main()
