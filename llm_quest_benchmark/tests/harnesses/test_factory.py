import pytest

from llm_quest_benchmark.agents.human_player import HumanPlayer
from llm_quest_benchmark.agents.random_agent import RandomAgent
from llm_quest_benchmark.harnesses.factory import HARNESS_REGISTRY, create_harness
from llm_quest_benchmark.harnesses.memo import MemoCompactHarness
from llm_quest_benchmark.harnesses.minimal import MinimalHarness
from llm_quest_benchmark.schemas.config import BenchmarkConfig, HarnessConfig


def test_create_minimal_harness():
    harness = create_harness("minimal", model="gpt-5-mini")

    assert isinstance(harness, MinimalHarness)


def test_all_harness_names_instantiate():
    for harness_name, harness_cls in HARNESS_REGISTRY.items():
        harness = create_harness(harness_name, model="gpt-5-mini")

        assert isinstance(harness, harness_cls)


def test_create_human_harness():
    harness = create_harness("human")

    assert isinstance(harness, HumanPlayer)


def test_create_random_choice_harness():
    harness = create_harness("random_choice")

    assert isinstance(harness, RandomAgent)


def test_create_bad_harness_name_raises():
    with pytest.raises(ValueError):
        create_harness("bad_name", model="gpt-5-mini")


def test_harness_config_stable_harness_id():
    config = HarnessConfig(harness="memo_compact", model="gpt-5-mini")

    assert isinstance(config.harness_id, str)
    assert config.harness_id == HarnessConfig(harness="memo_compact", model="gpt-5-mini").harness_id


def test_benchmark_config_from_yaml_parses_harness(tmp_path):
    quest_path = tmp_path / "quest.qm"
    quest_path.write_text("", encoding="utf-8")
    config_path = tmp_path / "benchmark.yaml"
    config_path.write_text(
        f"""
quests:
  - {quest_path}
agents:
  - model: gpt-5-mini
    harness: memo_compact
""",
        encoding="utf-8",
    )

    config = BenchmarkConfig.from_yaml(str(config_path))

    assert len(config.agents) == 1
    assert isinstance(config.agents[0], HarnessConfig)
    assert isinstance(create_harness(config.agents[0].harness, model=config.agents[0].model), MemoCompactHarness)
    assert config.agents[0].harness == "memo_compact"


def test_benchmark_config_from_yaml_rejects_template(tmp_path):
    quest_path = tmp_path / "quest.qm"
    quest_path.write_text("", encoding="utf-8")
    config_path = tmp_path / "benchmark.yaml"
    config_path.write_text(
        f"""
quests:
  - {quest_path}
agents:
  - model: gpt-5-mini
    template: reasoning.jinja
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Use 'harness:' instead of 'template:'"):
        BenchmarkConfig.from_yaml(str(config_path))
