"""Comprehensive tests for concrete harness behavior."""

from unittest.mock import Mock

from llm_quest_benchmark.harnesses.factory import HARNESS_REGISTRY, create_harness
from llm_quest_benchmark.harnesses.memo import (
    CompactionNoMemoHarness,
    HintedCompactHarness,
    MemoCompactHarness,
    MemoCotHarness,
    MemoExtendedHarness,
    MemoStructuredHarness,
)
from llm_quest_benchmark.harnesses.memory import CompactionMemory, DefaultMemory, FullTranscriptMemory
from llm_quest_benchmark.harnesses.minimal import MinimalHarness
from llm_quest_benchmark.harnesses.planner import PlannerHarness
from llm_quest_benchmark.harnesses.reasoning import ReasoningFullTranscriptHarness, ReasoningRecentHarness
from llm_quest_benchmark.harnesses.tool_harness import ToolCompactHarness, ToolHintedHarness

HARNESS_SPECS = {
    "minimal": (MinimalHarness, "stub.jinja", DefaultMemory),
    "reasoning_recent": (ReasoningRecentHarness, "reasoning.jinja", DefaultMemory),
    "reasoning_full": (ReasoningFullTranscriptHarness, "reasoning.jinja", FullTranscriptMemory),
    "memo_compact": (MemoCompactHarness, "stateful_compact.jinja", CompactionMemory),
    "hinted_compact": (HintedCompactHarness, "stateful_compact_hints.jinja", CompactionMemory),
    "tool_compact": (ToolCompactHarness, "tool_augmented.jinja", CompactionMemory),
    "tool_hinted": (ToolHintedHarness, "tool_augmented_hints.jinja", CompactionMemory),
    "planner": (PlannerHarness, "planner.jinja", CompactionMemory),
    "compaction_no_memo": (CompactionNoMemoHarness, "reasoning.jinja", CompactionMemory),
    "memo_cot": (MemoCotHarness, "memo_cot.jinja", CompactionMemory),
    "memo_extended": (MemoExtendedHarness, "memo_extended.jinja", CompactionMemory),
    "memo_structured": (MemoStructuredHarness, "memo_structured.jinja", CompactionMemory),
}


def assert_harness_configuration(harness_name: str) -> None:
    expected_class, expected_template, expected_memory_class = HARNESS_SPECS[harness_name]

    harness = create_harness(harness_name, model="gpt-5-mini")

    assert isinstance(harness, expected_class)
    assert harness.harness_name == harness_name
    assert harness.action_template == expected_template
    assert isinstance(harness.memory_module, expected_memory_class)


def test_minimal_harness_configuration():
    assert_harness_configuration("minimal")


def test_reasoning_recent_harness_configuration():
    assert_harness_configuration("reasoning_recent")


def test_reasoning_full_harness_configuration():
    assert_harness_configuration("reasoning_full")


def test_memo_compact_harness_configuration():
    assert_harness_configuration("memo_compact")


def test_hinted_compact_harness_configuration():
    assert_harness_configuration("hinted_compact")


def test_tool_compact_harness_configuration():
    assert_harness_configuration("tool_compact")


def test_tool_hinted_harness_configuration():
    assert_harness_configuration("tool_hinted")


def test_planner_harness_configuration():
    assert_harness_configuration("planner")


def test_exp4_retired_harness_configuration():
    assert_harness_configuration("compaction_no_memo")
    assert_harness_configuration("memo_cot")
    assert_harness_configuration("memo_extended")
    assert_harness_configuration("memo_structured")


def test_all_registry_harnesses_have_configuration_specs():
    assert set(HARNESS_REGISTRY) == set(HARNESS_SPECS)


def test_all_registry_harnesses_instantiate_with_expected_names():
    for harness_name in HARNESS_REGISTRY:
        harness = create_harness(harness_name, model="gpt-5-mini")

        assert harness.harness_name == harness_name


def test_memo_compact_mocked_llm_returns_action_and_reuses_memo_context():
    harness = MemoCompactHarness(model_name="gpt-5-mini")
    mocked_llm = Mock()
    mocked_llm.get_completion.side_effect = [
        '{"memo":"Merchant needs fuel payment","analysis":"pay first","reasoning":"quest clue","result":2}',
        '{"memo":"Paid fuel merchant","analysis":"memo says paid","reasoning":"continue","result":1}',
    ]
    mocked_llm.get_last_usage.return_value = {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
        "estimated_cost_usd": 0.0,
    }
    harness.llm = mocked_llm

    first_action = harness.get_action("A merchant offers fuel for a fee.", [{"text": "Leave"}, {"text": "Pay"}])
    second_action = harness.get_action("The fuel gauge still blinks.", [{"text": "Check receipt"}, {"text": "Leave"}])

    assert first_action == 2
    assert second_action == 1
    assert harness.get_last_response().memo == "Paid fuel merchant"
    second_prompt = mocked_llm.get_completion.call_args_list[1].args[0]
    assert "Merchant needs fuel payment" in second_prompt


def test_compaction_memory_receives_existing_llm_client():
    harness = MemoCompactHarness(model_name="gpt-5-mini", compaction_interval=1)
    mocked_llm = Mock()
    mocked_llm.get_completion.side_effect = [
        '{"memo":"Paid fuel merchant","analysis":"pay first","reasoning":"quest clue","result":2}',
        "Summary: paid the fuel merchant and should keep receipt.",
    ]
    mocked_llm.get_last_usage.return_value = {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
        "estimated_cost_usd": 0.0,
    }
    harness.llm = mocked_llm

    action = harness.get_action("A merchant offers fuel for a fee.", [{"text": "Leave"}, {"text": "Pay"}])

    assert action == 2
    assert harness.memory_module.llm_client is mocked_llm
    assert harness.memory_module._compaction_summary == "Summary: paid the fuel merchant and should keep receipt."
    assert harness.memory_module.steps_since_compaction == 0


def test_planner_harness_first_turn_generates_plan_then_acts():
    harness = PlannerHarness(model_name="gpt-5-mini")
    mocked_llm = Mock()
    mocked_llm.get_completion.side_effect = [
        "Gather clues first. Avoid direct fights. Preserve resources.",
        '{"analysis":"plan says scout","reasoning":"safer branch","result":2}',
    ]
    mocked_llm.get_last_usage.side_effect = [
        {"prompt_tokens": 30, "completion_tokens": 12, "total_tokens": 42, "estimated_cost_usd": 0.001},
        {"prompt_tokens": 20, "completion_tokens": 8, "total_tokens": 28, "estimated_cost_usd": 0.0007},
    ]
    harness.llm = mocked_llm

    action = harness.get_action("You enter a pirate station.", [{"text": "Scout ahead"}, {"text": "Attack now"}])

    assert action == 2
    assert harness.current_plan is not None
    assert "Avoid direct fights" in harness.current_plan
    assert mocked_llm.get_completion.call_count == 2
    assert harness.get_last_response().total_tokens == 70


def test_planner_harness_reuses_plan_when_state_is_stable():
    harness = PlannerHarness(model_name="gpt-5-mini")
    harness.current_plan = "Keep moving carefully and avoid a direct fight."
    harness._observation_history = ["Quiet corridor."]
    mocked_llm = Mock()
    mocked_llm.get_completion.return_value = '{"analysis":"plan still fits","reasoning":"careful progress","result":1}'
    mocked_llm.get_last_usage.return_value = {
        "prompt_tokens": 18,
        "completion_tokens": 7,
        "total_tokens": 25,
        "estimated_cost_usd": 0.0005,
    }
    harness.llm = mocked_llm

    action = harness.get_action("Quiet corridor.", [{"text": "Open the door"}, {"text": "Run"}])

    assert action == 1
    assert mocked_llm.get_completion.call_count == 1


def test_planner_harness_uses_contextual_memory_state():
    harness = PlannerHarness(model_name="gpt-5-mini", compaction_interval=50)
    harness.memory_module.set_quest_briefing("Original mission: win the election.")
    harness.memory_module.transcript = [
        {
            "step": 1,
            "observation": "You learned Maloqs value strength.",
            "choice_text": "Ask about Maloqs",
            "memo": "Maloqs value strength",
            "action": 1,
        }
    ]
    harness.memory_module.steps_since_compaction = 1
    mocked_llm = Mock()
    mocked_llm.get_completion.side_effect = [
        "Use the remembered cultural clue.",
        '{"analysis":"use clue","reasoning":"fits plan","result":1}',
    ]
    mocked_llm.get_last_usage.return_value = {
        "prompt_tokens": 1,
        "completion_tokens": 1,
        "total_tokens": 2,
        "estimated_cost_usd": 0.0,
    }
    harness.llm = mocked_llm

    harness.get_action("Current banquet scene.", [{"text": "Greet like a warrior"}])

    first_prompt = mocked_llm.get_completion.call_args_list[0].args[0]
    assert "Quest briefing" in first_prompt
    assert "RECENT STEPS" in first_prompt
    assert "Maloqs value strength" in first_prompt


def test_tool_compact_harness_can_use_quest_history():
    harness = ToolCompactHarness(model_name="gpt-5-mini")
    harness._step_log = [
        {
            "step": 1,
            "observation": "Merchant mentioned low fuel.",
            "choices": ["Buy fuel", "Keep flying"],
            "selected_choice": "Buy fuel",
        }
    ]
    harness._history_tool.step_log = harness._step_log
    mocked_llm = Mock()
    mocked_llm.get_completion.side_effect = [
        '{"analysis":"need history","tool_calls":[{"tool":"quest_history","input":"fuel merchant"}],"result":null}',
        '{"analysis":"fuel clue matters","reasoning":"play safe","result":1}',
    ]
    mocked_llm.get_last_usage.side_effect = [
        {"prompt_tokens": 24, "completion_tokens": 10, "total_tokens": 34, "estimated_cost_usd": 0.0008},
        {"prompt_tokens": 22, "completion_tokens": 9, "total_tokens": 31, "estimated_cost_usd": 0.0007},
    ]
    harness.llm = mocked_llm

    action = harness.get_action("Your fuel gauge is blinking.", [{"text": "Refuel"}, {"text": "Attack pirates"}])

    assert action == 1
    assert mocked_llm.get_completion.call_count == 2
    assert harness.get_last_response().total_tokens == 65
    assert len(harness._step_log) == 2
    assert harness.get_last_response().tool_results
    assert "Merchant mentioned low fuel" in harness.get_last_response().tool_results[0]


def test_tool_compact_calculator_supports_arithmetic_and_comparisons():
    assert ToolCompactHarness.calculator("55 + 12 - 5") == "55 + 12 - 5 = 62"
    assert ToolCompactHarness.calculator("60 >= 55 and 62 >= 80") == "60 >= 55 and 62 >= 80 = False"
    assert ToolCompactHarness.calculator("__import__('os')").startswith("error:")


def test_tool_compact_scratchpad_read_write_and_reset():
    harness = ToolCompactHarness(model_name="gpt-5-mini")

    assert harness.scratchpad("read") == "(empty)"
    assert (
        harness.scratchpad("write_replace", " Board: W B _ ; failed door 2 ") == "updated: Board: W B _ ; failed door 2"
    )
    assert harness.scratchpad("read") == "Board: W B _ ; failed door 2"

    harness.reset()

    assert harness.scratchpad("read") == "(empty)"


def test_tool_compact_harness_can_use_calculator_and_records_tool_metadata():
    harness = ToolCompactHarness(model_name="gpt-5-mini")
    mocked_llm = Mock()
    mocked_llm.get_completion.side_effect = [
        '{"memo":"Need mix math","analysis":"calculate target","tool_calls":[{"tool":"calculator","input":"50 + 3 >= 55"}],"result":null}',
        '{"memo":"Need more strength","analysis":"math failed","reasoning":"choose strength","result":2}',
    ]
    mocked_llm.get_last_usage.return_value = {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
        "estimated_cost_usd": 0.0,
    }
    harness.llm = mocked_llm

    action = harness.get_action("Strength is 50. Need at least 55.", [{"text": "Add water"}, {"text": "Add repusator"}])

    response = harness.get_last_response()
    assert action == 2
    assert response.tool_calls == [{"tool": "calculator", "input": "50 + 3 >= 55", "operation": "", "content": ""}]
    assert response.tool_results == ["calculator(50 + 3 >= 55) => 50 + 3 >= 55 = False"]
    assert response.memo == "Need more strength"


def test_tool_compact_harness_can_use_scratchpad_tool_call():
    harness = ToolCompactHarness(model_name="gpt-5-mini")
    mocked_llm = Mock()
    mocked_llm.get_completion.side_effect = [
        (
            '{"analysis":"save board","tool_calls":[{"tool":"scratchpad",'
            '"operation":"write_replace","content":"Board: red blue blank"}],"result":null}'
        ),
        '{"analysis":"note saved","reasoning":"use saved board","result":1}',
    ]
    mocked_llm.get_last_usage.return_value = {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
        "estimated_cost_usd": 0.0,
    }
    harness.llm = mocked_llm

    action = harness.get_action("A colored board blocks the hall.", [{"text": "Use red-blue order"}])

    assert action == 1
    assert harness.scratchpad("read") == "Board: red blue blank"
    assert harness.get_last_response().tool_results == [
        "scratchpad(write_replace, Board: red blue blank) => updated: Board: red blue blank"
    ]


def test_tool_compact_harness_uses_contextual_memory_state():
    harness = ToolCompactHarness(model_name="gpt-5-mini", compaction_interval=50)
    harness.memory_module.set_quest_briefing("Original mission: pass pilot certification.")
    harness.memory_module.transcript = [
        {
            "step": 1,
            "observation": "Hogger is greedy.",
            "choice_text": "Bribe Hogger",
            "memo": "Hogger is greedy",
            "action": 1,
        }
    ]
    harness.memory_module.steps_since_compaction = 1
    mocked_llm = Mock()
    mocked_llm.get_completion.return_value = (
        '{"memo":"Hogger is greedy","analysis":"no tools needed","tool_calls":[],"result":1}'
    )
    mocked_llm.get_last_usage.return_value = {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
        "estimated_cost_usd": 0.0,
    }
    harness.llm = mocked_llm

    harness.get_action("Current exam room.", [{"text": "Offer a bribe"}])

    prompt = mocked_llm.get_completion.call_args.args[0]
    assert "Quest briefing" in prompt
    assert "RECENT STEPS" in prompt
    assert "Hogger is greedy" in prompt


def test_tool_compact_harness_can_finish_without_tools_in_one_call():
    harness = ToolCompactHarness(model_name="gpt-5-mini")
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
    harness.llm = mocked_llm

    action = harness.get_action("A guard points at the safe exit.", [{"text": "Fight"}, {"text": "Leave"}])

    assert action == 2
    assert mocked_llm.get_completion.call_count == 1
