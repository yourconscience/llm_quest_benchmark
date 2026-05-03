import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
QUEST_INDEX_PATH = REPO_ROOT / "site" / "play" / "quest-index.json"


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
