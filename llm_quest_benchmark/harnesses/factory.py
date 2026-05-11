"""Factory for creating harness-based quest players."""

from llm_quest_benchmark.agents.base import QuestPlayer
from llm_quest_benchmark.agents.human_player import HumanPlayer
from llm_quest_benchmark.agents.random_agent import RandomAgent
from llm_quest_benchmark.harnesses.memo import HintedCompactHarness, MemoCompactHarness
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
}


def create_harness(
    harness: str,
    model: str,
    temperature: float = 0.4,
    skip_single: bool = False,
    debug: bool = False,
    compaction_interval: int = 50,
    system_template: str = "system_role.jinja",
) -> QuestPlayer:
    if harness == "human":
        return HumanPlayer(skip_single=skip_single)
    if harness.startswith("random_choice"):
        seed = None
        if "_" in harness[13:]:
            try:
                seed = int(harness.split("_")[-1])
            except ValueError:
                pass
        return RandomAgent(seed=seed, debug=debug, skip_single=skip_single)
    if harness not in HARNESS_REGISTRY:
        raise ValueError(f"Unknown harness '{harness}'. Valid: {sorted(HARNESS_REGISTRY)}")
    cls = HARNESS_REGISTRY[harness]
    return cls(
        model_name=model,
        temperature=temperature,
        skip_single=skip_single,
        debug=debug,
        compaction_interval=compaction_interval,
        system_template=system_template,
    )
