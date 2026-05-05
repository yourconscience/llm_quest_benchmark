from llm_quest_benchmark.core.quest_lang import (
    EN_TO_RU_QUEST_MAP,
    RU_TO_EN_QUEST_MAP,
    SUPPORTED_LANGUAGES,
    available_ru_quest_ids,
    canonical_quest_id,
    quest_lang,
)


class TestCanonicalQuestId:
    def test_ru_maps_to_eng(self):
        assert canonical_quest_id("Banket_ru") == "Banket_eng"
        assert canonical_quest_id("Badday_ru") == "Badday_eng"
        assert canonical_quest_id("Pizza_ru") == "Pizza_eng"

    def test_eng_passes_through(self):
        assert canonical_quest_id("Banket_eng") == "Banket_eng"
        assert canonical_quest_id("Badday_eng") == "Badday_eng"

    def test_unknown_passes_through(self):
        assert canonical_quest_id("SomeNew_quest") == "SomeNew_quest"
        assert canonical_quest_id("unknown") == "unknown"

    def test_all_ru_entries_canonicalize(self):
        for ru_id, en_id in RU_TO_EN_QUEST_MAP.items():
            assert canonical_quest_id(ru_id) == en_id
            assert en_id.endswith("_eng")


class TestQuestLang:
    def test_ru_suffix(self):
        assert quest_lang("Banket_ru") == "ru"
        assert quest_lang("Badday_ru") == "ru"

    def test_eng_suffix(self):
        assert quest_lang("Banket_eng") == "en"

    def test_no_suffix(self):
        assert quest_lang("Boat") == "en"


class TestMappingConsistency:
    def test_maps_are_inverses(self):
        for ru_id, en_id in RU_TO_EN_QUEST_MAP.items():
            assert EN_TO_RU_QUEST_MAP[en_id] == ru_id

    def test_same_length(self):
        assert len(RU_TO_EN_QUEST_MAP) == len(EN_TO_RU_QUEST_MAP)

    def test_available_ru_quest_ids(self):
        ids = available_ru_quest_ids()
        assert len(ids) == 18
        assert all(qid.endswith("_ru") for qid in ids)

    def test_supported_languages(self):
        assert "en" in SUPPORTED_LANGUAGES
        assert "ru" in SUPPORTED_LANGUAGES


class TestLeaderboardCanonicalization:
    """Verify that leaderboard grouping uses canonical IDs."""

    def test_ru_quest_groups_with_eng(self, tmp_path, monkeypatch):
        import json

        monkeypatch.chdir(tmp_path)

        from llm_quest_benchmark.core.leaderboard import generate_leaderboard

        benchmark_dir = tmp_path / "results" / "benchmarks" / "bench_canon"
        benchmark_dir.mkdir(parents=True)

        results = [
            {
                "quest": "quests/sr_2_1_2121_eng/Banket_eng.qm",
                "model": "openai:gpt-4",
                "template": "stub.jinja",
                "agent_id": "test_agent",
                "attempt": 1,
                "outcome": "SUCCESS",
                "reward": 1.0,
                "error": None,
            },
            {
                "quest": "quests/sr_2_dominators_ru/Banket_ru.qm",
                "model": "openai:gpt-4",
                "template": "stub.jinja",
                "agent_id": "test_agent",
                "attempt": 1,
                "outcome": "FAILURE",
                "reward": 0.0,
                "error": None,
            },
        ]

        summary = {
            "benchmark_id": "canon_test",
            "results": results,
            "db_runs": [],
        }
        (benchmark_dir / "benchmark_summary.json").write_text(json.dumps(summary))

        output_path = str(tmp_path / "leaderboard.json")
        leaderboard = generate_leaderboard(
            [str(benchmark_dir)],
            output_path,
            min_runs=0,
            public_model_ids=None,
        )

        quest_ids = [r["quest"] for r in leaderboard["results"]]
        assert "Banket_ru" not in quest_ids
        assert "Banket_eng" in quest_ids

        banket_rows = [r for r in leaderboard["results"] if r["quest"] == "Banket_eng"]
        assert len(banket_rows) == 1
        assert banket_rows[0]["runs"] == 2
        assert banket_rows[0]["success_rate"] == 0.5

        banket_quest = [q for q in leaderboard["quests"] if q["id"] == "Banket_eng"][0]
        assert banket_quest["lang"] == "EN"
        assert banket_quest["source_langs"] == ["EN", "RU"]
