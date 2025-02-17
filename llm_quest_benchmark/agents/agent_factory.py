"""Factory for creating quest agents"""
import logging
from typing import Optional

from llm_quest_benchmark.agents.base import QuestPlayer
from llm_quest_benchmark.agents.llm_agent import LLMAgent
from llm_quest_benchmark.agents.random_agent import RandomAgent
from llm_quest_benchmark.agents.human_player import HumanPlayer
from llm_quest_benchmark.constants import DEFAULT_MODEL, DEFAULT_TEMPLATE, DEFAULT_TEMPERATURE

logger = logging.getLogger(__name__)

def create_agent(
    model: str = DEFAULT_MODEL,
    debug: bool = False,
    template: str = DEFAULT_TEMPLATE,
    skip_single: bool = False,
    temperature: float = DEFAULT_TEMPERATURE,
) -> QuestPlayer:
    """Create a quest agent based on model name and parameters.

    Args:
        model (str): Model identifier. Can be:
            - LLM model name (e.g. 'gpt-4o', 'sonnet')
            - 'random_choice' for random testing agent (can include seed e.g. 'random_choice_123')
            - 'human' for interactive human player
        debug (bool): Enable debug logging
        template (str): Prompt template for LLM agents
        skip_single (bool): Auto-select single choices
        temperature (float): Temperature for LLM sampling

    Returns:
        QuestPlayer: Appropriate agent instance

    Raises:
        ValueError: If model type is not recognized
    """
    logger.debug(f"Creating agent for model: {model}")

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

    # Default to LLM agent
    return LLMAgent(
        debug=debug,
        model_name=model,
        template=template,
        skip_single=skip_single,
        temperature=temperature
    )