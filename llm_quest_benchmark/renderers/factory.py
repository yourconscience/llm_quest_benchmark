"""Factory for creating appropriate renderers based on agent type and mode"""
from typing import Optional, Type

from llm_quest_benchmark.agents.base import QuestPlayer
from llm_quest_benchmark.agents.human_player import HumanPlayer
from llm_quest_benchmark.renderers.base import BaseRenderer
from llm_quest_benchmark.renderers.null import NoRenderer
from llm_quest_benchmark.renderers.progress import ProgressRenderer
from llm_quest_benchmark.renderers.terminal import RichRenderer


def create_renderer(agent: QuestPlayer,
                    debug: bool = False,
                    total_quests: Optional[int] = None,
                    total_runs: Optional[int] = None) -> BaseRenderer:
    """Create appropriate renderer based on agent type and mode

    Args:
        agent (QuestPlayer): The agent that will be using the renderer
        debug (bool, optional): Whether debug mode is enabled. Defaults to False.
        total_quests (Optional[int], optional): Total number of quests for progress bar. Defaults to None.
        total_runs (Optional[int], optional): Total number of runs for progress bar. Defaults to None.

    Returns:
        BaseRenderer: The appropriate renderer instance

    The factory follows these rules:
    1. In debug mode, always use NoRenderer
    2. For human players, use RichRenderer
    3. For automated agents (LLM, Random):
       - In benchmark mode (total_quests provided), use ProgressRenderer
       - Otherwise, use NoRenderer
    """
    if debug:
        return NoRenderer()
    elif total_quests is not None and total_runs is not None:
        # In benchmark mode, always use ProgressRenderer
        return ProgressRenderer(total_quests, total_runs)
    elif isinstance(agent, HumanPlayer):
        return RichRenderer()
    else:
        return NoRenderer()
