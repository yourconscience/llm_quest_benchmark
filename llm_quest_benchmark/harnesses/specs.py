"""Canonical harness specifications and treatment signatures.

A harness specification declares the material components of a treatment:
prompt, memory, tools, loop, and reasoning policy. Reports read those
components directly instead of inferring them from harness names.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from llm_quest_benchmark.schemas.records import canonical_json

# Memory policies.
MEMORY_NONE = "none"
MEMORY_RECENT_WINDOW = "recent_window"
MEMORY_FULL_TRANSCRIPT = "full_transcript"
MEMORY_COMPACTION = "compaction"

# Decision loop policies.
LOOP_SINGLE_CALL = "single_call"
LOOP_TOOL_SELECT_ACT = "tool_select_act"
LOOP_PLAN_ACT = "plan_act"
LOOP_CHOOSE_OR_RESTORE = "choose_or_restore"
LOOP_ADAPTIVE_DEPTH = "adaptive_depth"
LOOP_INTERACTIVE = "interactive"
LOOP_RANDOM = "random"

# Reasoning policies.
REASONING_NONE = "none"
REASONING_CONCISE = "concise"
REASONING_CHAIN_OF_THOUGHT = "chain_of_thought"
REASONING_STRUCTURED = "structured"
REASONING_PLAN = "plan"
REASONING_ADAPTIVE = "adaptive"

COMPACTION_TOOLS = ("calculator", "scratchpad", "quest_history")
PROGRAMMATIC_TOOLS = ("calculator", "scratchpad", "history_read", "history_search")


@dataclass(frozen=True)
class HarnessSpec:
    """Material description of one harness treatment."""

    name: str
    prompt: str
    memory: str
    loop: str
    reasoning: str
    tools: tuple[str, ...] = ()
    knobs: tuple[str, ...] = ()
    experimental: bool = False
    requires_model: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "harness": self.name,
            "prompt": self.prompt,
            "memory": self.memory,
            "tools": list(self.tools),
            "loop": self.loop,
            "reasoning": self.reasoning,
        }


HARNESS_SPECS: dict[str, HarnessSpec] = {
    "minimal": HarnessSpec(
        name="minimal",
        prompt="stub.jinja",
        memory=MEMORY_RECENT_WINDOW,
        loop=LOOP_SINGLE_CALL,
        reasoning=REASONING_NONE,
    ),
    "reasoning_recent": HarnessSpec(
        name="reasoning_recent",
        prompt="reasoning.jinja",
        memory=MEMORY_RECENT_WINDOW,
        loop=LOOP_SINGLE_CALL,
        reasoning=REASONING_CONCISE,
    ),
    "reasoning_full": HarnessSpec(
        name="reasoning_full",
        prompt="reasoning.jinja",
        memory=MEMORY_FULL_TRANSCRIPT,
        loop=LOOP_SINGLE_CALL,
        reasoning=REASONING_CONCISE,
    ),
    "memo_compact": HarnessSpec(
        name="memo_compact",
        prompt="stateful_compact.jinja",
        memory=MEMORY_COMPACTION,
        loop=LOOP_SINGLE_CALL,
        reasoning=REASONING_CONCISE,
        knobs=("compaction_interval",),
    ),
    "hinted_compact": HarnessSpec(
        name="hinted_compact",
        prompt="stateful_compact_hints.jinja",
        memory=MEMORY_COMPACTION,
        loop=LOOP_SINGLE_CALL,
        reasoning=REASONING_CONCISE,
        knobs=("compaction_interval",),
    ),
    "tool_compact": HarnessSpec(
        name="tool_compact",
        prompt="tool_augmented.jinja",
        memory=MEMORY_COMPACTION,
        loop=LOOP_TOOL_SELECT_ACT,
        reasoning=REASONING_CONCISE,
        tools=COMPACTION_TOOLS,
        knobs=("compaction_interval",),
    ),
    "tool_hinted": HarnessSpec(
        name="tool_hinted",
        prompt="tool_augmented_hints.jinja",
        memory=MEMORY_COMPACTION,
        loop=LOOP_TOOL_SELECT_ACT,
        reasoning=REASONING_CONCISE,
        tools=COMPACTION_TOOLS,
        knobs=("compaction_interval",),
    ),
    "programmatic_memory": HarnessSpec(
        name="programmatic_memory",
        prompt="programmatic_memory.jinja",
        memory=MEMORY_RECENT_WINDOW,
        loop=LOOP_TOOL_SELECT_ACT,
        reasoning=REASONING_CONCISE,
        tools=PROGRAMMATIC_TOOLS,
    ),
    "planner": HarnessSpec(
        name="planner",
        prompt="planner.jinja",
        memory=MEMORY_COMPACTION,
        loop=LOOP_PLAN_ACT,
        reasoning=REASONING_PLAN,
        knobs=("compaction_interval",),
    ),
    "compaction_no_memo": HarnessSpec(
        name="compaction_no_memo",
        prompt="reasoning.jinja",
        memory=MEMORY_COMPACTION,
        loop=LOOP_SINGLE_CALL,
        reasoning=REASONING_CONCISE,
        knobs=("compaction_interval",),
    ),
    "memo_cot": HarnessSpec(
        name="memo_cot",
        prompt="memo_cot.jinja",
        memory=MEMORY_COMPACTION,
        loop=LOOP_SINGLE_CALL,
        reasoning=REASONING_CHAIN_OF_THOUGHT,
        knobs=("compaction_interval",),
    ),
    "memo_extended": HarnessSpec(
        name="memo_extended",
        prompt="memo_extended.jinja",
        memory=MEMORY_COMPACTION,
        loop=LOOP_SINGLE_CALL,
        reasoning=REASONING_CONCISE,
        knobs=("compaction_interval",),
    ),
    "memo_structured": HarnessSpec(
        name="memo_structured",
        prompt="memo_structured.jinja",
        memory=MEMORY_COMPACTION,
        loop=LOOP_SINGLE_CALL,
        reasoning=REASONING_STRUCTURED,
        knobs=("compaction_interval",),
    ),
    "backtracking": HarnessSpec(
        name="backtracking",
        prompt="backtracking.jinja",
        memory=MEMORY_COMPACTION,
        loop=LOOP_CHOOSE_OR_RESTORE,
        reasoning=REASONING_CONCISE,
        knobs=("compaction_interval", "restore_limit"),
        experimental=True,
    ),
    "adaptive_reasoning": HarnessSpec(
        name="adaptive_reasoning",
        prompt="adaptive_reasoning.jinja",
        memory=MEMORY_RECENT_WINDOW,
        loop=LOOP_ADAPTIVE_DEPTH,
        reasoning=REASONING_ADAPTIVE,
        knobs=("adaptive_stall_steps",),
        experimental=True,
    ),
    "human": HarnessSpec(
        name="human",
        prompt="none",
        memory=MEMORY_NONE,
        loop=LOOP_INTERACTIVE,
        reasoning=REASONING_NONE,
        requires_model=False,
    ),
    "random_choice": HarnessSpec(
        name="random_choice",
        prompt="none",
        memory=MEMORY_NONE,
        loop=LOOP_RANDOM,
        reasoning=REASONING_NONE,
        knobs=("seed",),
        requires_model=False,
    ),
}

# Harnesses that support restoring a recorded checkpoint.
RESTORE_HARNESSES = frozenset(name for name, spec in HARNESS_SPECS.items() if spec.loop == LOOP_CHOOSE_OR_RESTORE)

# Knobs that are only meaningful for a specific harness.
EXCLUSIVE_KNOBS = {
    "restore_limit": "backtracking",
    "adaptive_stall_steps": "adaptive_reasoning",
}

LLM_HARNESS_NAMES = tuple(sorted(name for name, spec in HARNESS_SPECS.items() if spec.requires_model))
SPECIAL_HARNESSES = ("human", "random_choice", "random_choice_<seed>")


def parse_random_choice_seed(identifier: str) -> tuple[bool, int | None]:
    """Return ``(is_random_choice, seed)`` for a harness or model identifier."""
    if identifier == "random_choice":
        return True, None
    prefix = "random_choice_"
    if identifier.startswith(prefix) and identifier[len(prefix) :].isdigit():
        return True, int(identifier[len(prefix) :])
    return False, None


def is_random_choice_harness(identifier: str) -> bool:
    is_random, _ = parse_random_choice_seed(identifier)
    return is_random


def get_spec(harness: str) -> HarnessSpec:
    """Resolve a harness identifier to its canonical specification."""
    is_random, _ = parse_random_choice_seed(harness)
    if is_random:
        return HARNESS_SPECS["random_choice"]
    spec = HARNESS_SPECS.get(harness)
    if spec is None:
        valid = [*sorted(HARNESS_SPECS), "random_choice_<seed>"]
        raise ValueError(f"Unknown harness '{harness}'. Valid: {valid}")
    return spec


def valid_harness_names() -> list[str]:
    return [*sorted(HARNESS_SPECS), "random_choice_<seed>"]


@dataclass
class HarnessTreatment:
    """Canonical, hashable description of one executed treatment."""

    harness: str
    prompt: str
    memory: str
    tools: list[str]
    loop: str
    reasoning: str
    model: str
    temperature: float
    system_prompt: str
    knobs: dict[str, Any] = field(default_factory=dict)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "harness": self.harness,
            "prompt": self.prompt,
            "memory": self.memory,
            "tools": sorted(self.tools),
            "loop": self.loop,
            "reasoning": self.reasoning,
            "model": self.model,
            "temperature": round(float(self.temperature), 6),
            "system_prompt": self.system_prompt,
            "knobs": {k: self.knobs[k] for k in sorted(self.knobs)},
        }

    @property
    def signature(self) -> str:
        digest = hashlib.sha256(canonical_json(self.canonical_payload()).encode("utf-8")).hexdigest()
        return f"t2_{digest[:16]}"

    def to_dict(self) -> dict[str, Any]:
        payload = self.canonical_payload()
        payload["signature"] = self.signature
        return payload

    @classmethod
    def unknown(cls, harness: str, model: str, temperature: float) -> HarnessTreatment:
        """Treatment for a configuration whose components cannot be resolved.

        Migration uses this for legacy records; it records an explicit
        ``unknown`` component rather than guessing a compatibility alias.
        """
        return cls(
            harness=harness or "unknown",
            prompt="unknown",
            memory="unknown",
            tools=[],
            loop="unknown",
            reasoning="unknown",
            model=model or "unknown",
            temperature=float(temperature or 0.0),
            system_prompt="unknown",
            knobs={},
        )


def build_treatment(
    harness: str,
    model: str,
    temperature: float,
    system_template: str,
    knob_values: dict[str, Any] | None = None,
) -> HarnessTreatment:
    """Build the canonical treatment for a harness configuration.

    Only knobs declared material by the harness specification enter the
    signature, so an irrelevant knob can never split otherwise-equal runs.
    """
    spec = get_spec(harness)
    knob_values = knob_values or {}
    knobs: dict[str, Any] = {}
    for knob in spec.knobs:
        value = knob_values.get(knob)
        if value is not None:
            knobs[knob] = value

    is_random, seed = parse_random_choice_seed(harness)
    if is_random and seed is not None:
        knobs["seed"] = seed

    return HarnessTreatment(
        harness=harness,
        prompt=spec.prompt,
        memory=spec.memory,
        tools=list(spec.tools),
        loop=spec.loop,
        reasoning=spec.reasoning,
        model=model,
        temperature=float(temperature),
        system_prompt=system_template if spec.requires_model else "none",
        knobs=knobs,
    )


def validate_exclusive_knobs(harness: str, knob_values: dict[str, Any]) -> None:
    """Reject harness-exclusive knobs supplied for a different harness."""
    for knob, owner in EXCLUSIVE_KNOBS.items():
        if knob_values.get(knob) is None:
            continue
        if harness != owner:
            raise ValueError(f"{knob} is only valid for harness: {owner}, got harness: {harness}")
