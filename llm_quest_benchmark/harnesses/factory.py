"""Factory for creating harness-based quest players."""

from llm_quest_benchmark.agents.base import QuestPlayer
from llm_quest_benchmark.agents.human_player import HumanPlayer
from llm_quest_benchmark.agents.random_agent import RandomAgent
from llm_quest_benchmark.constants import DEFAULT_MODEL
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
from llm_quest_benchmark.harnesses.tool_harness import ToolCompactHarness, ToolHintedHarness

HARNESS_REGISTRY = {
    "minimal": MinimalHarness,
    "reasoning_recent": ReasoningRecentHarness,
    "reasoning_full": ReasoningFullTranscriptHarness,
    "memo_compact": MemoCompactHarness,
    "hinted_compact": HintedCompactHarness,
    "tool_compact": ToolCompactHarness,
    "tool_hinted": ToolHintedHarness,
    "planner": PlannerHarness,
    "compaction_no_memo": CompactionNoMemoHarness,
    "memo_cot": MemoCotHarness,
    "memo_extended": MemoExtendedHarness,
    "memo_structured": MemoStructuredHarness,
}

SPECIAL_HARNESSES = ("human", "random_choice", "random_choice_<seed>")


def _parse_random_choice_seed(identifier: str) -> tuple[bool, int | None]:
    if identifier == "random_choice":
        return True, None
    prefix = "random_choice_"
    if identifier.startswith(prefix) and identifier[len(prefix) :].isdigit():
        return True, int(identifier[len(prefix) :])
    return False, None


def is_random_choice_harness(identifier: str) -> bool:
    is_random, _ = _parse_random_choice_seed(identifier)
    return is_random


def create_harness(
    harness: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.4,
    skip_single: bool = False,
    debug: bool = False,
    compaction_interval: int = 50,
    system_template: str = "system_role.jinja",
) -> QuestPlayer:
    valid = [*sorted(HARNESS_REGISTRY), *SPECIAL_HARNESSES]
    is_random_harness, seed = _parse_random_choice_seed(harness)
    is_random_model, _ = _parse_random_choice_seed(model)
    if is_random_harness:
        if is_random_model and model != "random_choice":
            raise ValueError("Encode random seeds in harness, for example harness='random_choice_123'")
        if model not in (DEFAULT_MODEL, "random_choice"):
            raise ValueError("Use model='random_choice' with random_choice harnesses")
        return RandomAgent(seed=seed, debug=debug, skip_single=skip_single)
    if harness.startswith("random_choice"):
        raise ValueError(f"Unknown harness '{harness}'. Valid: {valid}")
    if harness == "human":
        return HumanPlayer(skip_single=skip_single)
    if harness not in HARNESS_REGISTRY:
        raise ValueError(f"Unknown harness '{harness}'. Valid: {valid}")
    if is_random_model:
        raise ValueError(
            "Use harness='random_choice' for random policy runs instead of pairing random_choice model with an LLM harness"
        )
    if model.startswith("random_choice"):
        raise ValueError(f"Unknown random_choice model '{model}'. Valid: {valid}")
    if model == "human":
        raise ValueError("Use harness='human' for human runs instead of pairing human model with an LLM harness")
    cls = HARNESS_REGISTRY[harness]
    return cls(
        model_name=model,
        temperature=temperature,
        skip_single=skip_single,
        debug=debug,
        compaction_interval=compaction_interval,
        system_template=system_template,
    )
