import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
QUEST_INDEX_PATH = REPO_ROOT / "site" / "play" / "quest-index.json"
APP_SOURCE_PATH = REPO_ROOT / "site" / "play" / "app.jsx"
APP_COMPILED_PATH = REPO_ROOT / "site" / "play" / "app.js"


def test_ru_quests_share_canonical_en_card_data():
    index = json.loads(QUEST_INDEX_PATH.read_text(encoding="utf-8"))
    quests = {quest["id"]: quest for quest in index["quests"]}

    ru_quests = [quest for quest in quests.values() if quest.get("lang") == "ru"]
    assert ru_quests

    for ru_quest in ru_quests:
        canonical_id = ru_quest.get("canonical_id")
        assert canonical_id, f"{ru_quest['id']} should point at canonical EN data"
        assert canonical_id in quests, f"{ru_quest['id']} points at missing {canonical_id}"

        en_quest = quests[canonical_id]
        assert ru_quest["win_rate"] == en_quest["win_rate"], ru_quest["id"]
        assert ru_quest["total_runs"] == en_quest["total_runs"], ru_quest["id"]


def test_play_uses_canonical_location_for_cohort_lookup():
    lookup_pattern = re.compile(
        r"const\s+locationId\s*=\s*canonicalPlayer\s*\?"
        r"\s*canonicalPlayer\.getSaving\(\)\.locationId\s*:"
        r"\s*player\.getSaving\(\)\.locationId\s*;"
    )

    for path in [APP_SOURCE_PATH, APP_COMPILED_PATH]:
        source = path.read_text(encoding="utf-8")
        assert lookup_pattern.search(source), path
        assert "const cohortId = quest.canonical_id || quest.id;" in source, path
