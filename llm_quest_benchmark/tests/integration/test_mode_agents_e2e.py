"""Integration tests for planner/tool harness modes on real quest execution loops."""

from pathlib import Path

import pytest

from llm_quest_benchmark.core.runner import run_quest_with_timeout
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.harnesses.factory import create_harness

QUEST_PATHS = [
    "quests/Boat.qm",
    "quests/sr_2_1_2121_eng/Banket_eng.qm",
    "quests/sr_2_1_2121_eng/Borzukhan_eng.qm",
]


class FakeLLM:
    def __init__(self, mode: str):
        self.mode = mode
        self._last_usage = {
            "prompt_tokens": 12,
            "completion_tokens": 6,
            "total_tokens": 18,
            "estimated_cost_usd": 0.0,
        }

    def get_completion(self, prompt: str) -> str:
        if self.mode == "planner" and "Write a short plan in 3-5 sentences." in prompt:
            return "Gather clues, avoid obvious risks, and take the safest route to progress."
        if self.mode == "tool" and "Decide whether you need a tool before choosing an action." in prompt:
            return '{"analysis":"no tool needed","tool_calls":[],"result":1}'
        return '{"analysis":"safe branch","reasoning":"first option progresses","result":1}'

    def get_last_usage(self):
        return self._last_usage


@pytest.mark.timeout(15)
@pytest.mark.skipif(not Path(QUEST_PATHS[1]).exists(), reason="Quest files not downloaded")
def test_planner_harness_runs_three_quests_across_openai_and_anthropic_models(monkeypatch):
    requested_models = []

    def fake_get_llm_client(model_name, **kwargs):
        requested_models.append(model_name)
        return FakeLLM("planner")

    monkeypatch.setattr("llm_quest_benchmark.harnesses.base.get_llm_client", fake_get_llm_client)

    for model_name in ["gpt-5-mini", "claude-sonnet-4-5"]:
        for quest_path in QUEST_PATHS:
            agent = create_harness("planner", model=model_name, skip_single=True)
            outcome = run_quest_with_timeout(quest_path, agent, timeout=10)
            assert outcome in {QuestOutcome.SUCCESS, QuestOutcome.FAILURE, QuestOutcome.TIMEOUT}
            assert outcome != QuestOutcome.ERROR

    assert requested_models.count("gpt-5-mini") == 3
    assert requested_models.count("claude-sonnet-4-5") == 3


@pytest.mark.timeout(15)
@pytest.mark.skipif(not Path(QUEST_PATHS[1]).exists(), reason="Quest files not downloaded")
def test_tool_harness_runs_three_quests(monkeypatch):
    monkeypatch.setattr(
        "llm_quest_benchmark.harnesses.base.get_llm_client",
        lambda model_name, **kwargs: FakeLLM("tool"),
    )

    for quest_path in QUEST_PATHS:
        agent = create_harness("tool_compact", model="gpt-5-mini", skip_single=True)
        outcome = run_quest_with_timeout(quest_path, agent, timeout=10)
        assert outcome in {QuestOutcome.SUCCESS, QuestOutcome.FAILURE, QuestOutcome.TIMEOUT}
        assert outcome != QuestOutcome.ERROR


@pytest.mark.timeout(15)
@pytest.mark.skipif(not Path(QUEST_PATHS[1]).exists(), reason="Quest files not downloaded")
def test_reused_mode_harnesses_reset_between_quest_runs():
    quest_path = "quests/sr_2_1_2121_eng/Borzukhan_eng.qm"
    planner_agent = create_harness("planner", model="gpt-5-mini", skip_single=True)
    planner_agent.llm = FakeLLM("planner")

    first_outcome = run_quest_with_timeout(quest_path, planner_agent, timeout=10)
    planner_agent.current_plan = "stale plan from previous run"
    planner_agent._plan_history = ["stale plan from previous run"]
    planner_agent._observation_history = ["stale observation"]
    second_outcome = run_quest_with_timeout(quest_path, planner_agent, timeout=10)

    assert first_outcome != QuestOutcome.ERROR
    assert second_outcome != QuestOutcome.ERROR
    assert planner_agent.current_plan != "stale plan from previous run"
    assert "stale plan from previous run" not in planner_agent._plan_history
    assert "stale observation" not in planner_agent._observation_history

    tool_agent = create_harness("tool_compact", model="gpt-5-mini", skip_single=True)
    tool_agent.llm = FakeLLM("tool")

    first_outcome = run_quest_with_timeout(quest_path, tool_agent, timeout=10)
    tool_agent._step_log = [
        {
            "step": 999,
            "observation": "stale observation",
            "choices": ["old choice"],
            "selected_choice": "old choice",
        }
    ]
    second_outcome = run_quest_with_timeout(quest_path, tool_agent, timeout=10)

    assert first_outcome != QuestOutcome.ERROR
    assert second_outcome != QuestOutcome.ERROR
    assert tool_agent._step_log
    assert tool_agent._step_log[0]["step"] != 999
    assert all(entry["observation"] != "stale observation" for entry in tool_agent._step_log)
