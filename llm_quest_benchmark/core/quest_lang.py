"""Pure functions for quest language mapping and canonicalization."""

SUPPORTED_LANGUAGES = ("en", "ru")

RU_TO_EN_QUEST_MAP: dict[str, str] = {
    "Banket_ru": "Banket_eng",
    "Badday_ru": "Badday_eng",
    "Pizza_ru": "Pizza_eng",
    "Borzukhan_ru": "Borzukhan_eng",
    "Ski_ru": "Ski_eng",
    "Election_ru": "Election_eng",
    "Robots_ru": "Robots_eng",
    "Leonardo_ru": "Leonardo_eng",
    "Depth_ru": "Depth_eng",
    "Edelweiss_ru": "Edelweiss_eng",
    "Ministry_ru": "Ministry_eng",
    "Foncers_ru": "Foncers_eng",
    "Driver_ru": "Driver_eng",
    "Codebox_ru": "Codebox_eng",
    "Pilot_ru": "Pilot_eng",
    "Sortirovka1_ru": "Sortirovka1_eng",
    "Shashki_ru": "Shashki_eng",
    "Player_ru": "Player_eng",
}

EN_TO_RU_QUEST_MAP: dict[str, str] = {v: k for k, v in RU_TO_EN_QUEST_MAP.items()}


def canonical_quest_id(quest_id: str) -> str:
    return RU_TO_EN_QUEST_MAP.get(quest_id, quest_id)


def quest_lang(quest_id: str) -> str:
    return "ru" if quest_id.endswith("_ru") else "en"


def available_ru_quest_ids() -> list[str]:
    return list(RU_TO_EN_QUEST_MAP.keys())
