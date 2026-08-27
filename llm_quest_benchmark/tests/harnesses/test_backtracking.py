"""Tests for the experimental backtracking harness."""

from unittest.mock import Mock

from llm_quest_benchmark.harnesses.backtracking import BacktrackingHarness, parse_restore_request
from llm_quest_benchmark.harnesses.factory import create_harness
from llm_quest_benchmark.harnesses.specs import HARNESS_SPECS, RESTORE_HARNESSES
from llm_quest_benchmark.players.base import DecisionContext
from llm_quest_benchmark.schemas.records import QuestSnapshot

CHOICES = [{"id": "11", "text": "Press on"}, {"id": "12", "text": "Turn back"}]


def _snapshot(location_id: str) -> QuestSnapshot:
    return QuestSnapshot(
        location_id=location_id,
        observation=f"You are at {location_id}",
        choices=CHOICES,
        params_state=["HP: 10"],
        saving={"locationId": location_id},
    )


def _context(checkpoints=3, restore_allowed=True, remaining=2) -> DecisionContext:
    return DecisionContext(
        step=checkpoints,
        checkpoints=[_snapshot(f"loc{i}") for i in range(checkpoints)],
        restore_allowed=restore_allowed,
        restores_remaining=remaining,
    )


def _mock_llm(*responses):
    llm = Mock()
    llm.get_completion.side_effect = list(responses)
    llm.get_last_usage.return_value = {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
        "estimated_cost_usd": 0.0,
    }
    return llm


def test_backtracking_is_the_only_restore_capable_harness():
    assert {"backtracking"} == RESTORE_HARNESSES
    assert BacktrackingHarness.supports_restore is True

    for name, spec in HARNESS_SPECS.items():
        if name == "backtracking":
            continue
        harness = create_harness(name, model="gpt-5-mini" if spec.requires_model else name)
        assert harness.supports_restore is False, f"{name} must not be able to restore"


def test_other_harnesses_cannot_emit_restore_actions():
    harness = create_harness("reasoning_recent", model="gpt-5-mini")
    harness.llm = _mock_llm('{"action":"restore","checkpoint":1,"result":2}')

    action = harness.get_quest_action("state", CHOICES, _context())

    assert action.is_choose
    assert action.checkpoint_index is None


def test_parse_restore_request_accepts_explicit_restore():
    assert parse_restore_request('{"action":"restore","checkpoint":2,"result":1}', 3) == 2
    assert parse_restore_request('{"restore":1}', 3) == 1


def test_parse_restore_request_rejects_out_of_range_and_non_restore():
    assert parse_restore_request('{"action":"restore","checkpoint":9}', 3) is None
    assert parse_restore_request('{"action":"restore","checkpoint":0}', 3) is None
    assert parse_restore_request('{"action":"choose","result":1}', 3) is None
    assert parse_restore_request("not json at all", 3) is None
    # No restorable checkpoint means no restore, whatever the model asked for.
    assert parse_restore_request('{"action":"restore","checkpoint":1}', 0) is None


def test_backtracking_harness_returns_a_restore_action():
    harness = BacktrackingHarness(model_name="gpt-5-mini")
    harness.llm = _mock_llm('{"action":"restore","analysis":"dead end","checkpoint":1,"result":2}')

    action = harness.get_quest_action("You are stuck.", CHOICES, _context())

    assert action.is_restore
    assert action.checkpoint_index == 1
    # The response still carries a usable fallback action if the runner rejects it.
    assert harness.get_last_response().action == 2
    assert harness.get_last_response().parse_mode == "restore"


def test_backtracking_harness_returns_a_choose_action_by_default():
    harness = BacktrackingHarness(model_name="gpt-5-mini")
    harness.llm = _mock_llm('{"action":"choose","analysis":"keep going","reasoning":"r","result":1}')

    action = harness.get_quest_action("You are fine.", CHOICES, _context())

    assert action.is_choose
    assert action.choice_index == 1


def test_backtracking_harness_ignores_restore_when_it_is_not_allowed():
    harness = BacktrackingHarness(model_name="gpt-5-mini")
    harness.llm = _mock_llm('{"action":"restore","checkpoint":1,"result":2}')

    action = harness.get_quest_action("Budget spent.", CHOICES, _context(restore_allowed=False, remaining=0))

    assert action.is_choose
    assert action.choice_index == 2


def test_backtracking_prompt_lists_restorable_checkpoints_and_budget():
    harness = BacktrackingHarness(model_name="gpt-5-mini")
    harness.llm = _mock_llm('{"action":"choose","result":1}')

    harness.get_quest_action("Current scene.", CHOICES, _context(checkpoints=3, remaining=2))
    prompt = harness.llm.get_completion.call_args_list[0].args[0]

    assert "[1] location loc0" in prompt
    assert "[2] location loc1" in prompt
    # The current state is the last checkpoint and is never offered for restore.
    assert "[3] location loc2" not in prompt
    assert "Restores remaining: 2" in prompt


def test_backtracking_prompt_omits_restore_when_unavailable():
    harness = BacktrackingHarness(model_name="gpt-5-mini")
    harness.llm = _mock_llm('{"action":"choose","result":1}')

    harness.get_quest_action("Current scene.", CHOICES, _context(restore_allowed=False))
    prompt = harness.llm.get_completion.call_args_list[0].args[0]

    assert "No checkpoint restore is available" in prompt
    assert "must choose an action" in prompt


def test_backtracking_harness_defaults_to_a_bounded_restore_limit():
    assert BacktrackingHarness(model_name="gpt-5-mini").restore_limit == 3
    assert BacktrackingHarness(model_name="gpt-5-mini", restore_limit=1).restore_limit == 1


def test_backtracking_harness_skips_single_choice_states_without_restoring():
    harness = BacktrackingHarness(model_name="gpt-5-mini", skip_single=True)
    harness.llm = _mock_llm()

    action = harness.get_quest_action("Only one door.", [{"id": "1", "text": "Enter"}], _context())

    assert action.is_choose
    assert action.choice_index == 1
    assert harness.llm.get_completion.call_count == 0


def test_backtracking_harness_recovers_from_provider_errors():
    harness = BacktrackingHarness(model_name="gpt-5-mini")
    llm = Mock()
    llm.get_completion.side_effect = RuntimeError("provider unavailable")
    llm.get_last_usage.return_value = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    harness.llm = llm

    action = harness.get_quest_action("Broken.", CHOICES, _context())

    assert action.is_choose
    assert action.choice_index == 1
    assert harness.get_last_response().is_default is True


def test_backtracking_reset_clears_pending_restore_state():
    harness = BacktrackingHarness(model_name="gpt-5-mini")
    harness.llm = _mock_llm('{"action":"restore","checkpoint":1,"result":1}')
    harness.get_quest_action("Stuck.", CHOICES, _context())

    harness.reset()

    assert harness._pending_restore is None
    assert harness._context.checkpoints == []
