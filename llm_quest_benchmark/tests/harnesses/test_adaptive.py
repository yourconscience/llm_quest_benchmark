"""Tests for the experimental adaptive-reasoning harness."""

from unittest.mock import Mock

from llm_quest_benchmark.harnesses.adaptive import MODE_CONCISE, MODE_DEEP, AdaptiveReasoningHarness
from llm_quest_benchmark.players.base import DecisionContext
from llm_quest_benchmark.schemas.records import ProgressState

CHOICES = [{"id": "11", "text": "Search the room"}, {"id": "12", "text": "Leave"}]


def _context(stalled: int = 0, current: float = 20.0) -> DecisionContext:
    return DecisionContext(progress=ProgressState(current=current, stalled_transitions=stalled))


def _mock_llm(*responses):
    llm = Mock()
    llm.get_completion.side_effect = list(responses) or ['{"analysis":"a","reasoning":"r","result":1}']
    llm.get_last_usage.return_value = {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
        "estimated_cost_usd": 0.0,
    }
    return llm


def _decide(harness, observation, context):
    harness.llm = _mock_llm('{"analysis":"a","reasoning":"r","result":1}')
    action = harness.get_quest_action(observation, CHOICES, context)
    prompt = harness.llm.get_completion.call_args_list[0].args[0]
    return action, prompt


def test_routine_states_use_concise_mode():
    harness = AdaptiveReasoningHarness(model_name="gpt-5-mini")

    action, prompt = _decide(harness, "A quiet corridor.", _context())

    assert action.is_choose
    assert harness.reasoning_mode == MODE_CONCISE
    assert "Concise mode." in prompt
    assert "Deep planning mode" not in prompt


def test_progress_stall_switches_the_next_decision_to_deep_mode():
    harness = AdaptiveReasoningHarness(model_name="gpt-5-mini", adaptive_stall_steps=3)

    _, concise_prompt = _decide(harness, "Scene one.", _context(stalled=2))
    assert harness.reasoning_mode == MODE_CONCISE
    assert "Concise mode." in concise_prompt

    _, deep_prompt = _decide(harness, "Scene two.", _context(stalled=3))
    assert harness.reasoning_mode == MODE_DEEP
    assert "Deep planning mode" in deep_prompt
    assert "progress_stalled_3" in deep_prompt


def test_repeated_state_switches_to_deep_mode():
    harness = AdaptiveReasoningHarness(model_name="gpt-5-mini")

    _decide(harness, "The same locked door.", _context())
    assert harness.reasoning_mode == MODE_CONCISE

    _, prompt = _decide(harness, "The same locked door.", _context())

    assert harness.reasoning_mode == MODE_DEEP
    assert "repeated_state" in prompt


def test_recovery_resets_the_trigger_without_losing_history():
    harness = AdaptiveReasoningHarness(model_name="gpt-5-mini", adaptive_stall_steps=2)

    _decide(harness, "Scene one.", _context(stalled=0))
    _decide(harness, "Scene two.", _context(stalled=2))
    assert harness.reasoning_mode == MODE_DEEP
    history_before = len(harness._decision_history)

    # A new milestone resets the stall counter and the state is not a repeat.
    _, prompt = _decide(harness, "A brand new hall.", _context(stalled=0))

    assert harness.reasoning_mode == MODE_CONCISE
    assert "Concise mode." in prompt
    assert len(harness._decision_history) == history_before + 1
    assert len(harness.history) == 3


def test_adaptive_harness_defaults_to_a_bounded_stall_trigger():
    assert AdaptiveReasoningHarness(model_name="gpt-5-mini").adaptive_stall_steps == 3
    assert AdaptiveReasoningHarness(model_name="gpt-5-mini", adaptive_stall_steps=7).adaptive_stall_steps == 7


def test_reset_returns_the_harness_to_concise_mode():
    harness = AdaptiveReasoningHarness(model_name="gpt-5-mini")
    _decide(harness, "Scene.", _context(stalled=9))
    assert harness.reasoning_mode == MODE_DEEP

    harness.reset()

    assert harness.reasoning_mode == MODE_CONCISE
    assert harness._context.progress.stalled_transitions == 0


def test_adaptive_harness_recovers_from_provider_errors():
    harness = AdaptiveReasoningHarness(model_name="gpt-5-mini")
    llm = Mock()
    llm.get_completion.side_effect = RuntimeError("provider unavailable")
    llm.get_last_usage.return_value = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    harness.llm = llm

    action = harness.get_quest_action("Broken.", CHOICES, _context())

    assert action.is_choose
    assert action.choice_index == 1
    assert harness.get_last_response().is_default is True
