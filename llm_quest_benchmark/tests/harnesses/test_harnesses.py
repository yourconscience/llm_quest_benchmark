"""Comprehensive tests for concrete harness behavior."""

from unittest.mock import Mock

from llm_quest_benchmark.harnesses.adaptive import AdaptiveReasoningHarness
from llm_quest_benchmark.harnesses.backtracking import BacktrackingHarness
from llm_quest_benchmark.harnesses.factory import HARNESS_CLASSES, create_harness
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
from llm_quest_benchmark.harnesses.tool_harness import ProgrammaticMemoryHarness, ToolCompactHarness, ToolHintedHarness
from llm_quest_benchmark.schemas.records import QuestAction, QuestSnapshot, QuestTransition

HARNESS_CONFIGURATIONS = {
    "minimal": (MinimalHarness, "stub.jinja", DefaultMemory),
    "reasoning_recent": (ReasoningRecentHarness, "reasoning.jinja", DefaultMemory),
    "reasoning_full": (ReasoningFullTranscriptHarness, "reasoning.jinja", FullTranscriptMemory),
    "memo_compact": (MemoCompactHarness, "stateful_compact.jinja", CompactionMemory),
    "hinted_compact": (HintedCompactHarness, "stateful_compact_hints.jinja", CompactionMemory),
    "tool_compact": (ToolCompactHarness, "tool_augmented.jinja", CompactionMemory),
    "tool_hinted": (ToolHintedHarness, "tool_augmented_hints.jinja", CompactionMemory),
    "programmatic_memory": (ProgrammaticMemoryHarness, "programmatic_memory.jinja", DefaultMemory),
    "planner": (PlannerHarness, "planner.jinja", CompactionMemory),
    "compaction_no_memo": (CompactionNoMemoHarness, "reasoning.jinja", CompactionMemory),
    "memo_cot": (MemoCotHarness, "memo_cot.jinja", CompactionMemory),
    "memo_extended": (MemoExtendedHarness, "memo_extended.jinja", CompactionMemory),
    "memo_structured": (MemoStructuredHarness, "memo_structured.jinja", CompactionMemory),
    "backtracking": (BacktrackingHarness, "backtracking.jinja", CompactionMemory),
    "adaptive_reasoning": (AdaptiveReasoningHarness, "adaptive_reasoning.jinja", DefaultMemory),
}


def assert_harness_configuration(harness_name: str) -> None:
    expected_class, expected_template, expected_memory_class = HARNESS_CONFIGURATIONS[harness_name]

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


def test_programmatic_memory_harness_configuration():
    assert_harness_configuration("programmatic_memory")


def test_planner_harness_configuration():
    assert_harness_configuration("planner")


def test_exp4_retired_harness_configuration():
    assert_harness_configuration("compaction_no_memo")
    assert_harness_configuration("memo_cot")
    assert_harness_configuration("memo_extended")
    assert_harness_configuration("memo_structured")


def test_all_registry_harnesses_have_configuration_specs():
    assert set(HARNESS_CLASSES) == set(HARNESS_CONFIGURATIONS)


def test_all_registry_harnesses_instantiate_with_expected_names():
    for harness_name in HARNESS_CLASSES:
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


# --- programmatic_memory harness ---------------------------------------------


def _mock_llm(*responses, usage=None):
    mocked_llm = Mock()
    mocked_llm.get_completion.side_effect = list(responses)
    mocked_llm.get_last_usage.return_value = usage or {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
        "estimated_cost_usd": 0.0,
    }
    return mocked_llm


def _record_executed_step(
    harness: ProgrammaticMemoryHarness,
    observation: str,
    choices: list[dict[str, str]],
    action: int,
) -> QuestTransition:
    """Deliver the post-env-step lifecycle event a runner would emit."""
    index = len(harness._trajectory) + 1
    before = QuestSnapshot(
        location_id="test",
        observation=observation,
        choices=[{"id": str(i + 1), "text": c.get("text", "")} for i, c in enumerate(choices)],
        saving={"locationId": index},
    )
    transition = QuestTransition(
        index=index,
        before=before,
        action=QuestAction.choose(action, str(action), 1735689600000 + index),
        after=QuestSnapshot(location_id="test", observation="after", saving={"locationId": index + 1}),
        response=harness.get_last_response(),
    )
    harness.on_transition(transition)
    return transition


def test_programmatic_memory_harness_can_use_history_search():
    harness = ProgrammaticMemoryHarness(model_name="gpt-5-mini")
    harness.llm = _mock_llm(
        '{"analysis":"no tools needed","tool_calls":[],"result":1}',
        '{"analysis":"need history","tool_calls":[{"tool":"history_search","input":"fuel"}],"result":null}',
        '{"analysis":"fuel clue matters","reasoning":"play safe","result":2}',
    )
    first_observation = "Merchant mentions low fuel."
    first_choices = [{"text": "Buy fuel"}, {"text": "Keep flying"}]
    first_action = harness.get_action(first_observation, first_choices)
    first_transition = _record_executed_step(harness, first_observation, first_choices, first_action)

    second_observation = "Your fuel gauge is blinking."
    second_choices = [{"text": "Refuel"}, {"text": "Attack pirates"}]
    action = harness.get_action(second_observation, second_choices)

    assert action == 2
    response = harness.get_last_response()
    assert response.tool_calls[0]["tool"] == "history_search"
    assert response.tool_results
    assert "Merchant mentions low fuel" in response.tool_results[0]
    assert harness._trajectory.recent(1)[0] is first_transition
    _record_executed_step(harness, second_observation, second_choices, action)
    assert len(harness._trajectory) == 2


def test_programmatic_memory_harness_can_use_history_read():
    harness = ProgrammaticMemoryHarness(model_name="gpt-5-mini")
    harness.llm = _mock_llm(
        '{"analysis":"no tools needed","tool_calls":[],"result":1}',
        (
            '{"analysis":"check chronology","tool_calls":['
            '{"tool":"history_read","start_step":1,"count":1}],"result":null}'
        ),
        '{"analysis":"order confirms it","reasoning":"go north","result":1}',
    )
    first_observation = "You are in the entry hall."
    first_choices = [{"text": "Look around"}, {"text": "Leave"}]
    first_action = harness.get_action(first_observation, first_choices)
    _record_executed_step(harness, first_observation, first_choices, first_action)

    second_observation = "The hall splits into two paths."
    second_choices = [{"text": "North"}, {"text": "South"}]
    action = harness.get_action(second_observation, second_choices)

    assert action == 1
    response = harness.get_last_response()
    assert response.tool_calls == [
        {
            "tool": "history_read",
            "input": "",
            "start_step": 1,
            "count": 1,
            "limit": None,
            "operation": "",
            "content": "",
        }
    ]
    assert "You are in the entry hall" in response.tool_results[0]


def test_programmatic_memory_harness_permits_at_most_one_retrieval_call():
    harness = ProgrammaticMemoryHarness(model_name="gpt-5-mini")
    harness.llm = _mock_llm(
        (
            '{"analysis":"need two","tool_calls":['
            '{"tool":"history_search","input":"a"},{"tool":"calculator","input":"1+1"}],"result":null}'
        ),
        '{"analysis":"done","reasoning":"one call only","result":1}',
    )
    observation = "Some state."
    choices = [{"text": "A"}, {"text": "B"}]
    action = harness.get_action(observation, choices)
    _record_executed_step(harness, observation, choices, action)

    response = harness.get_last_response()
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0]["tool"] == "history_search"
    assert len(response.tool_results) == 1
    assert harness.llm.get_completion.call_count == 2  # select + final only, no second tool round


def test_programmatic_memory_harness_reuses_calculator_and_scratchpad_unchanged():
    harness = ProgrammaticMemoryHarness(model_name="gpt-5-mini")

    assert ProgrammaticMemoryHarness.calculator("2 + 2") == "2 + 2 = 4"
    assert harness.scratchpad("read") == "(empty)"
    assert harness.scratchpad("write_replace", "note") == "updated: note"
    assert harness.scratchpad("read") == "note"


def test_programmatic_memory_harness_prompt_has_single_recent_context_source():
    """DefaultMemory is the only bounded recent-context source in the select
    prompt. The trajectory contributes no second recent-context block -- only
    on-demand history_read/history_search retrieval, exercised separately."""
    harness = ProgrammaticMemoryHarness(model_name="gpt-5-mini")
    choices = [{"text": "A"}, {"text": "B"}]
    for i in range(3):
        observation = f"Observation number {i + 1}."
        harness.llm = _mock_llm('{"analysis":"ok","tool_calls":[],"reasoning":"r","result":1}')
        action = harness.get_action(observation, choices)
        _record_executed_step(harness, observation, choices, action)

    harness.llm = _mock_llm('{"analysis":"ok","tool_calls":[],"reasoning":"r","result":1}')
    harness.get_action("Observation number 4.", choices)
    prompt = harness.llm.get_completion.call_args_list[0].args[0]

    assert "Recent context from previous steps" in prompt  # DefaultMemory block
    assert "Recent quest history:" not in prompt  # no separate trajectory block
    assert "Observation number 1" in prompt  # DefaultMemory's own previous-steps window
    assert harness._recent_steps() == []


def test_programmatic_memory_harness_reset_clears_trajectory():
    harness = ProgrammaticMemoryHarness(model_name="gpt-5-mini")
    harness.llm = _mock_llm('{"analysis":"ok","tool_calls":[],"reasoning":"r","result":1}')
    observation = "Some state."
    choices = [{"text": "A"}]
    action = harness.get_action(observation, choices)
    _record_executed_step(harness, observation, choices, action)

    assert len(harness._trajectory) == 1

    harness.reset()

    assert len(harness._trajectory) == 0
    assert harness.scratchpad("read") == "(empty)"


# --- programmatic_memory canonical lifecycle bookkeeping ---------------------


def test_programmatic_memory_normal_path_appends_exactly_one_step():
    harness = ProgrammaticMemoryHarness(model_name="gpt-5-mini")
    harness.llm = _mock_llm('{"analysis":"ok","tool_calls":[],"reasoning":"r","result":2}')
    observation = "Normal state."
    choices = [{"text": "A"}, {"text": "B"}]

    action = harness.get_action(observation, choices)
    transition = _record_executed_step(harness, observation, choices, action)

    assert action == 2
    assert len(harness._trajectory) == 1
    assert harness._trajectory.recent(1)[0] is transition
    assert transition.action.choice_index == 2


def test_programmatic_memory_retry_path_appends_exactly_one_step():
    harness = ProgrammaticMemoryHarness(model_name="gpt-5-mini")
    harness.llm = _mock_llm(
        "not parseable at all",
        '{"analysis":"recovered","reasoning":"r","result":2}',
    )
    observation = "State needing retry."
    choices = [{"text": "A"}, {"text": "B"}]

    action = harness.get_action(observation, choices)
    _record_executed_step(harness, observation, choices, action)

    assert action == 2
    assert len(harness._trajectory) == 1


def test_programmatic_memory_safety_override_path_appends_exactly_one_step():
    harness = ProgrammaticMemoryHarness(model_name="gpt-5-mini")
    harness.llm = _mock_llm('{"analysis":"go","tool_calls":[],"reasoning":"r","result":1}')
    choices = [
        {"text": "Пойти в космопорт и улететь, чтобы завтра не позориться"},
        {"text": "Постараться пройти мимо"},
    ]

    action = harness.get_action("Risky moment.", choices)
    transition = _record_executed_step(harness, "Risky moment.", choices, action)

    assert action == 2  # safety filter overrides the risky first choice
    assert len(harness._trajectory) == 1
    assert transition.action.choice_index == 2
    assert transition.before.choices[1]["text"] == "Постараться пройти мимо"


def test_programmatic_memory_error_default_path_appends_exactly_one_step():
    harness = ProgrammaticMemoryHarness(model_name="gpt-5-mini")
    mocked_llm = Mock()
    mocked_llm.get_completion.side_effect = RuntimeError("provider unavailable")
    mocked_llm.get_last_usage.return_value = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "estimated_cost_usd": None,
    }
    harness.llm = mocked_llm
    observation = "Broken state."
    choices = [{"text": "A"}, {"text": "B"}]

    action = harness.get_action(observation, choices)
    _record_executed_step(harness, observation, choices, action)

    assert action == 1
    assert harness.get_last_response().is_default is True
    assert harness.get_last_response().parse_mode == "error_default"
    assert len(harness._trajectory) == 1
    assert harness._trajectory.recent(1)[0].action.choice_index == 1


def test_programmatic_memory_skip_single_path_appends_exactly_one_step():
    harness = ProgrammaticMemoryHarness(model_name="gpt-5-mini", skip_single=True)
    observation = "Only one door here."
    choices = [{"text": "Open the only door"}]

    action = harness.get_action(observation, choices)
    transition = _record_executed_step(harness, observation, choices, action)

    assert action == 1
    assert harness.get_last_response().reasoning == "auto_single_choice"
    assert len(harness._trajectory) == 1
    assert transition.action.choice_index == 1
    assert transition.before.choices[0]["text"] == "Open the only door"


def test_programmatic_memory_multi_turn_bookkeeping_stays_exactly_one_per_turn():
    """Mixed decision paths never double- or under-count lifecycle events."""
    harness = ProgrammaticMemoryHarness(model_name="gpt-5-mini")
    choices = [{"text": "A"}, {"text": "B"}]

    harness.llm = _mock_llm('{"analysis":"ok","tool_calls":[],"reasoning":"r","result":1}')
    action = harness.get_action("Turn 1 normal.", choices)
    _record_executed_step(harness, "Turn 1 normal.", choices, action)

    mocked_llm = Mock()
    mocked_llm.get_completion.side_effect = RuntimeError("boom")
    mocked_llm.get_last_usage.return_value = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "estimated_cost_usd": None,
    }
    harness.llm = mocked_llm
    action = harness.get_action("Turn 2 errors.", choices)
    _record_executed_step(harness, "Turn 2 errors.", choices, action)

    harness.llm = _mock_llm('{"analysis":"ok","tool_calls":[],"reasoning":"r","result":1}')
    single_choice = [{"text": "Only choice"}]
    action = harness.get_action("Turn 3 single choice, LLM path since skip_single is off.", single_choice)
    _record_executed_step(harness, "Turn 3 single choice, LLM path since skip_single is off.", single_choice, action)

    assert [t.index for t in harness._trajectory.recent(10)] == [1, 2, 3]
