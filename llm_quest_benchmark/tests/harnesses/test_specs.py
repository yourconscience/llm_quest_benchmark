"""Tests for canonical harness specifications and treatment signatures."""

import json

import pytest

from llm_quest_benchmark.harnesses.specs import (
    HARNESS_SPECS,
    HarnessTreatment,
    build_treatment,
    get_spec,
    valid_harness_names,
    validate_exclusive_knobs,
)


def _treatment(**overrides) -> HarnessTreatment:
    kwargs = {
        "harness": "reasoning_recent",
        "model": "gpt-5-mini",
        "temperature": 0.4,
        "system_template": "system_role.jinja",
    }
    kwargs.update(overrides)
    return build_treatment(**kwargs)


def test_every_spec_declares_all_material_components():
    for name, spec in HARNESS_SPECS.items():
        assert spec.name == name
        assert spec.prompt
        assert spec.memory
        assert spec.loop
        assert spec.reasoning
        assert isinstance(spec.tools, tuple)


def test_treatment_serializes_the_declared_components():
    treatment = _treatment(harness="tool_compact", knob_values={"compaction_interval": 25})
    payload = treatment.to_dict()

    assert payload["harness"] == "tool_compact"
    assert payload["prompt"] == "tool_augmented.jinja"
    assert payload["memory"] == "compaction"
    assert payload["loop"] == "tool_select_act"
    assert payload["tools"] == sorted(["calculator", "scratchpad", "quest_history"])
    assert payload["knobs"] == {"compaction_interval": 25}
    assert payload["signature"].startswith("t2_")


def test_equivalent_configurations_hash_identically():
    first = _treatment()
    second = _treatment()

    assert first.signature == second.signature
    assert json.dumps(first.to_dict(), sort_keys=True) == json.dumps(second.to_dict(), sort_keys=True)


def test_material_differences_produce_different_signatures():
    base = _treatment().signature

    assert _treatment(harness="reasoning_full").signature != base
    assert _treatment(model="gpt-5-nano").signature != base
    assert _treatment(temperature=0.7).signature != base
    assert _treatment(system_template="other.jinja").signature != base
    assert (
        _treatment(harness="memo_compact", knob_values={"compaction_interval": 10}).signature
        != _treatment(harness="memo_compact", knob_values={"compaction_interval": 50}).signature
    )


def test_irrelevant_knobs_do_not_split_otherwise_equal_treatments():
    """A knob a harness does not declare must never enter its signature."""
    with_knob = _treatment(knob_values={"compaction_interval": 10, "restore_limit": 5})
    without_knob = _treatment(knob_values={})

    assert with_knob.signature == without_knob.signature
    assert with_knob.knobs == {}


def test_random_choice_seed_is_a_material_knob():
    seeded = build_treatment("random_choice_7", "random_choice", 0.0, "none")
    unseeded = build_treatment("random_choice", "random_choice", 0.0, "none")

    assert seeded.knobs["seed"] == 7
    assert seeded.signature != unseeded.signature


def test_non_model_harnesses_record_no_system_prompt():
    for harness in ("human", "random_choice"):
        payload = build_treatment(harness, harness, 0.0, "system_role.jinja").to_dict()
        assert payload["system_prompt"] == "none"


def test_unknown_treatment_is_explicit_and_hashable():
    unknown = HarnessTreatment.unknown("legacy_thing", "old-model", 0.3)
    payload = unknown.to_dict()

    assert payload["prompt"] == "unknown"
    assert payload["memory"] == "unknown"
    assert payload["loop"] == "unknown"
    assert payload["reasoning"] == "unknown"
    assert payload["signature"].startswith("t2_")


def test_get_spec_resolves_seeded_random_choice_and_rejects_unknown_names():
    assert get_spec("random_choice_42").name == "random_choice"
    assert get_spec("memo_compact").name == "memo_compact"

    with pytest.raises(ValueError, match="Unknown harness"):
        get_spec("not_a_harness")


def test_valid_harness_names_include_the_seeded_random_form():
    names = valid_harness_names()

    assert "random_choice_<seed>" in names
    assert "backtracking" in names
    assert "adaptive_reasoning" in names


def test_exclusive_knobs_are_rejected_for_other_harnesses():
    validate_exclusive_knobs("backtracking", {"restore_limit": 2})
    validate_exclusive_knobs("adaptive_reasoning", {"adaptive_stall_steps": 2})
    validate_exclusive_knobs("memo_compact", {"restore_limit": None})

    with pytest.raises(ValueError, match="restore_limit is only valid for harness: backtracking"):
        validate_exclusive_knobs("memo_compact", {"restore_limit": 2})

    with pytest.raises(ValueError, match="adaptive_stall_steps is only valid for harness: adaptive_reasoning"):
        validate_exclusive_knobs("planner", {"adaptive_stall_steps": 2})
