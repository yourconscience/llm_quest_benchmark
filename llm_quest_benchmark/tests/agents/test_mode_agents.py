"""Tests for planner and tool-augmented agent modes."""
from unittest.mock import Mock

from llm_quest_benchmark.agents.agent_factory import create_agent
from llm_quest_benchmark.agents.llm_agent import LLMAgent
from llm_quest_benchmark.agents.planner_agent import PlannerAgent
from llm_quest_benchmark.agents.tool_agent import ToolAgent


def test_create_agent_uses_planner_template_alias():
    agent = create_agent(model="gpt-5-mini", action_template="planner")
    assert isinstance(agent, PlannerAgent)


def test_create_agent_uses_tool_template_alias():
    agent = create_agent(model="gpt-5-mini", action_template="tool_augmented")
    assert isinstance(agent, ToolAgent)


def test_create_agent_uses_light_hints_template_with_standard_llm_agent():
    agent = create_agent(model="gpt-5-mini", action_template="light_hints")
    assert isinstance(agent, LLMAgent)
    assert not isinstance(agent, (PlannerAgent, ToolAgent))


def test_light_hints_template_injects_general_mechanics():
    agent = LLMAgent(model_name="gpt-5-mini", action_template="light_hints")

    prompt = agent._format_prompt("A sealed vault blocks the route.", [{"text": "Study the vault"}])

    assert "General hints for this type of quest" in prompt
    assert "Preparation, study, negotiation" in prompt


def test_planner_agent_first_turn_generates_plan_then_acts():
    agent = PlannerAgent(model_name="gpt-5-mini")
    mocked_llm = Mock()
    mocked_llm.get_completion.side_effect = [
        "Gather clues first. Avoid direct fights. Preserve resources.",
        '{"analysis":"plan says scout","reasoning":"safer branch","result":2}',
    ]
    mocked_llm.get_last_usage.side_effect = [
        {"prompt_tokens": 30, "completion_tokens": 12, "total_tokens": 42, "estimated_cost_usd": 0.001},
        {"prompt_tokens": 20, "completion_tokens": 8, "total_tokens": 28, "estimated_cost_usd": 0.0007},
    ]
    agent.llm = mocked_llm

    action = agent.get_action("You enter a pirate station.", [{"text": "Scout ahead"}, {"text": "Attack now"}])

    assert action == 2
    assert agent.current_plan is not None
    assert "Avoid direct fights" in agent.current_plan
    assert mocked_llm.get_completion.call_count == 2
    assert agent.get_last_response().total_tokens == 70


def test_planner_agent_reuses_plan_when_state_is_stable():
    agent = PlannerAgent(model_name="gpt-5-mini")
    agent.current_plan = "Keep moving carefully and avoid a direct fight."
    agent._observation_history = ["Quiet corridor."]
    mocked_llm = Mock()
    mocked_llm.get_completion.return_value = '{"analysis":"plan still fits","reasoning":"careful progress","result":1}'
    mocked_llm.get_last_usage.return_value = {
        "prompt_tokens": 18,
        "completion_tokens": 7,
        "total_tokens": 25,
        "estimated_cost_usd": 0.0005,
    }
    agent.llm = mocked_llm

    action = agent.get_action("Quiet corridor.", [{"text": "Open the door"}, {"text": "Run"}])

    assert action == 1
    assert mocked_llm.get_completion.call_count == 1


def test_tool_agent_can_use_quest_history():
    agent = ToolAgent(model_name="gpt-5-mini")
    agent._step_log = [
        {
            "step": 1,
            "observation": "Merchant mentioned low fuel.",
            "choices": ["Buy fuel", "Keep flying"],
            "selected_choice": "Buy fuel",
        }
    ]
    mocked_llm = Mock()
    mocked_llm.get_completion.side_effect = [
        '{"analysis":"need history","tool_calls":[{"tool":"quest_history","input":"fuel merchant"}],"result":null}',
        '{"analysis":"fuel clue matters","reasoning":"play safe","result":1}',
    ]
    mocked_llm.get_last_usage.side_effect = [
        {"prompt_tokens": 24, "completion_tokens": 10, "total_tokens": 34, "estimated_cost_usd": 0.0008},
        {"prompt_tokens": 22, "completion_tokens": 9, "total_tokens": 31, "estimated_cost_usd": 0.0007},
    ]
    agent.llm = mocked_llm

    action = agent.get_action("Your fuel gauge is blinking.", [{"text": "Refuel"}, {"text": "Attack pirates"}])

    assert action == 1
    assert mocked_llm.get_completion.call_count == 2
    assert agent.get_last_response().total_tokens == 65
    assert len(agent._step_log) == 2


def test_tool_agent_can_finish_without_tools_in_one_call():
    agent = ToolAgent(model_name="gpt-5-mini")
    mocked_llm = Mock()
    mocked_llm.get_completion.return_value = (
        '{"analysis":"no tools needed","tool_calls":[],"reasoning":"direct clue","result":2}'
    )
    mocked_llm.get_last_usage.return_value = {
        "prompt_tokens": 15,
        "completion_tokens": 6,
        "total_tokens": 21,
        "estimated_cost_usd": 0.0004,
    }
    agent.llm = mocked_llm

    action = agent.get_action("A guard points at the safe exit.", [{"text": "Fight"}, {"text": "Leave"}])

    assert action == 2
    assert mocked_llm.get_completion.call_count == 1
