"""Factory for creating quest agents"""

import logging

from llm_quest_benchmark.agents.base import QuestPlayer
from llm_quest_benchmark.agents.human_player import HumanPlayer
from llm_quest_benchmark.agents.llm_agent import LLMAgent
from llm_quest_benchmark.agents.planner_agent import PlannerAgent
from llm_quest_benchmark.agents.random_agent import RandomAgent
from llm_quest_benchmark.agents.tool_agent import ToolAgent
from llm_quest_benchmark.constants import (
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    DEFAULT_TEMPLATE,
    SYSTEM_ROLE_TEMPLATE,
    normalize_template_name,
)

logger = logging.getLogger(__name__)


def create_agent(
    model: str = DEFAULT_MODEL,
    system_template: str = SYSTEM_ROLE_TEMPLATE,
    action_template: str = DEFAULT_TEMPLATE,
    temperature: float = DEFAULT_TEMPERATURE,
    skip_single: bool = False,
    debug: bool = False,
    memory_mode: str = "default",
    compaction_interval: int = 10,
) -> QuestPlayer:
    """Create a quest agent based on model name and parameters.

    Args:
        model (str): Model identifier. Can be:
            - LLM model name (e.g. 'gpt-5-mini', 'claude-sonnet-4-5')
            - 'random_choice' for random testing agent (can include seed e.g. 'random_choice_123')
            - 'human' for interactive human player
        debug (bool): Enable debug logging
        system_template (str): System template for LLM agents
        action_template (str): Action template for LLM agents
        temperature (float): Temperature for LLM sampling
        skip_single (bool): Auto-select single choices

    Returns:
        QuestPlayer: Appropriate agent instance

    Raises:
        ValueError: If model type is not recognized
    """
    logger.debug(f"Creating agent for model: {model}")
    resolved_action_template = normalize_template_name(action_template)

    # Human player
    if model == "human":
        return HumanPlayer(skip_single=skip_single)

    # Random choice agent
    if model.startswith("random_choice"):
        seed = None
        if "_" in model:
            try:
                seed = int(model.split("_")[-1])
            except ValueError:
                pass
        return RandomAgent(seed=seed, debug=debug, skip_single=skip_single)

    if resolved_action_template == "planner.jinja":
        return PlannerAgent(
            debug=debug,
            model_name=model,
            system_template=system_template,
            action_template=resolved_action_template,
            temperature=temperature,
            skip_single=skip_single,
            memory_mode=memory_mode,
            compaction_interval=compaction_interval,
        )

    if resolved_action_template == "tool_augmented.jinja":
        return ToolAgent(
            debug=debug,
            model_name=model,
            system_template=system_template,
            action_template=resolved_action_template,
            temperature=temperature,
            skip_single=skip_single,
            memory_mode=memory_mode,
            compaction_interval=compaction_interval,
        )

    # Default to LLM agent
    return LLMAgent(
        debug=debug,
        model_name=model,
        system_template=system_template,
        action_template=resolved_action_template,
        temperature=temperature,
        skip_single=skip_single,
        memory_mode=memory_mode,
        compaction_interval=compaction_interval,
    )
