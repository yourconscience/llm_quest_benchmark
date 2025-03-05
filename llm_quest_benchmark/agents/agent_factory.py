"""Factory for creating quest agents"""
import logging
from typing import Any, Dict, List, Optional

from llm_quest_benchmark.agents.agent_manager import AgentManager
from llm_quest_benchmark.agents.base import QuestPlayer
from llm_quest_benchmark.agents.human_player import HumanPlayer
from llm_quest_benchmark.agents.llm_agent import LLMAgent
from llm_quest_benchmark.agents.random_agent import RandomAgent
from llm_quest_benchmark.constants import (
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    DEFAULT_TEMPLATE,
    SYSTEM_ROLE_TEMPLATE,
)

logger = logging.getLogger(__name__)


def create_agent(
    model: str = DEFAULT_MODEL,
    system_template: str = SYSTEM_ROLE_TEMPLATE,
    action_template: str = DEFAULT_TEMPLATE,
    temperature: float = DEFAULT_TEMPERATURE,
    skip_single: bool = False,
    debug: bool = False,
    memory_config: Optional[Dict[str, Any]] = None,
    tools: Optional[List[str]] = None,
    agent_config: Optional[Dict[str, Any]] = None,
) -> QuestPlayer:
    """Create a quest agent based on model name and parameters.

    Args:
        model (str): Model identifier. Can be:
            - LLM model name (e.g. 'gpt-4o', 'sonnet')
            - 'random_choice' for random testing agent (can include seed e.g. 'random_choice_123')
            - 'human' for interactive human player
        debug (bool): Enable debug logging
        system_template (str): System template for LLM agents
        action_template (str): Action template for LLM agents
        temperature (float): Temperature for LLM sampling
        skip_single (bool): Auto-select single choices
        memory_config (Optional[Dict[str, Any]]): Memory configuration
        tools (Optional[List[str]]): List of tools available to the agent
        agent_config (Optional[Dict[str, Any]]): Complete agent configuration

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

    # Use agent_config if provided
    if agent_config:
        # Extract relevant parameters from agent_config
        model = agent_config.get("model", model)
        system_template = agent_config.get("system_template", system_template)
        action_template = agent_config.get("action_template", action_template)
        temperature = agent_config.get("temperature", temperature)
        memory_config = agent_config.get("memory")
        tools = agent_config.get("tools")

    # Default to LLM agent
    return LLMAgent(debug=debug,
                    model_name=model,
                    system_template=system_template,
                    action_template=action_template,
                    temperature=temperature,
                    skip_single=skip_single,
                    memory_config=memory_config,
                    tools=tools)


def create_agent_from_id(agent_id: str,
                         skip_single: bool = False,
                         debug: bool = False) -> Optional[QuestPlayer]:
    """Create an agent from a saved agent ID

    Args:
        agent_id (str): Agent ID to load
        skip_single (bool): Auto-select single choices
        debug (bool): Enable debug logging

    Returns:
        Optional[QuestPlayer]: Agent instance or None if not found
    """
    # Get agent configuration from agent manager
    agent_manager = AgentManager()
    agent_config = agent_manager.get_agent(agent_id)

    if not agent_config:
        logger.error(f"Agent ID not found: {agent_id}")
        return None

    # Create agent from config
    return create_agent(model=agent_config.model,
                        system_template=agent_config.system_template,
                        action_template=agent_config.action_template,
                        temperature=agent_config.temperature,
                        skip_single=skip_single,
                        debug=debug,
                        memory_config=agent_config.memory.dict() if agent_config.memory else None,
                        tools=agent_config.tools,
                        agent_config=agent_config.dict())
