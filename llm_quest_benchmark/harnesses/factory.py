"""Factory for creating harness-based quest players."""

from llm_quest_benchmark.constants import DEFAULT_MODEL
from llm_quest_benchmark.harnesses.adaptive import AdaptiveReasoningHarness
from llm_quest_benchmark.harnesses.backtracking import BacktrackingHarness
from llm_quest_benchmark.harnesses.memo import (
    CompactionNoMemoHarness,
    HintedCompactHarness,
    MemoCompactHarness,
    MemoCotHarness,
    MemoExtendedHarness,
    MemoStructuredHarness,
)
from llm_quest_benchmark.harnesses.minimal import MinimalHarness
from llm_quest_benchmark.harnesses.planner import PlannerHarness
from llm_quest_benchmark.harnesses.reasoning import ReasoningFullTranscriptHarness, ReasoningRecentHarness
from llm_quest_benchmark.harnesses.specs import (
    HARNESS_SPECS,
    SPECIAL_HARNESSES,
    is_random_choice_harness,
    parse_random_choice_seed,
    valid_harness_names,
)
from llm_quest_benchmark.harnesses.tool_harness import ProgrammaticMemoryHarness, ToolCompactHarness, ToolHintedHarness
from llm_quest_benchmark.players.base import QuestPlayer
from llm_quest_benchmark.players.human import HumanPlayer
from llm_quest_benchmark.players.random import RandomPlayer

__all__ = [
    "HARNESS_CLASSES",
    "HARNESS_SPECS",
    "SPECIAL_HARNESSES",
    "create_harness",
    "is_random_choice_harness",
]

# Implementation for each model-driven harness specification.
HARNESS_CLASSES = {
    "minimal": MinimalHarness,
    "reasoning_recent": ReasoningRecentHarness,
    "reasoning_full": ReasoningFullTranscriptHarness,
    "memo_compact": MemoCompactHarness,
    "hinted_compact": HintedCompactHarness,
    "tool_compact": ToolCompactHarness,
    "tool_hinted": ToolHintedHarness,
    "programmatic_memory": ProgrammaticMemoryHarness,
    "planner": PlannerHarness,
    "compaction_no_memo": CompactionNoMemoHarness,
    "memo_cot": MemoCotHarness,
    "memo_extended": MemoExtendedHarness,
    "memo_structured": MemoStructuredHarness,
    "backtracking": BacktrackingHarness,
    "adaptive_reasoning": AdaptiveReasoningHarness,
}


def create_harness(
    harness: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.4,
    skip_single: bool = False,
    debug: bool = False,
    compaction_interval: int = 50,
    system_template: str = "system_role.jinja",
    restore_limit: int | None = None,
    adaptive_stall_steps: int | None = None,
) -> QuestPlayer:
    valid = valid_harness_names()
    is_random_harness, seed = parse_random_choice_seed(harness)
    is_random_model, _ = parse_random_choice_seed(model)
    if is_random_harness:
        if is_random_model and model != "random_choice":
            raise ValueError("Encode random seeds in harness, for example harness='random_choice_123'")
        if model not in (DEFAULT_MODEL, "random_choice"):
            raise ValueError("Use model='random_choice' with random_choice harnesses")
        return RandomPlayer(seed=seed, debug=debug, skip_single=skip_single)
    if harness.startswith("random_choice"):
        raise ValueError(f"Unknown harness '{harness}'. Valid: {valid}")
    if harness == "human":
        return HumanPlayer(skip_single=skip_single)
    if harness not in HARNESS_CLASSES:
        raise ValueError(f"Unknown harness '{harness}'. Valid: {valid}")
    if is_random_model:
        raise ValueError(
            "Use harness='random_choice' for random policy runs instead of pairing random_choice model with an LLM harness"
        )
    if model.startswith("random_choice"):
        raise ValueError(f"Unknown random_choice model '{model}'. Valid: {valid}")
    if model == "human":
        raise ValueError("Use harness='human' for human runs instead of pairing human model with an LLM harness")

    spec = HARNESS_SPECS[harness]
    kwargs = {
        "model_name": model,
        "temperature": temperature,
        "skip_single": skip_single,
        "debug": debug,
        "compaction_interval": compaction_interval,
        "system_template": system_template,
    }
    if "restore_limit" in spec.knobs and restore_limit is not None:
        kwargs["restore_limit"] = restore_limit
    if "adaptive_stall_steps" in spec.knobs and adaptive_stall_steps is not None:
        kwargs["adaptive_stall_steps"] = adaptive_stall_steps
    return HARNESS_CLASSES[harness](**kwargs)
