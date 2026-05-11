__all__ = ["create_agent", "QuestPlayer", "RandomAgent", "LLMAgent", "PlannerAgent", "ToolAgent"]


def __getattr__(name):
    if name == "create_agent":
        from .agent_factory import create_agent

        return create_agent
    if name == "QuestPlayer":
        from .base import QuestPlayer

        return QuestPlayer
    if name == "RandomAgent":
        from .random_agent import RandomAgent

        return RandomAgent
    if name == "LLMAgent":
        from .llm_agent import LLMAgent

        return LLMAgent
    if name == "PlannerAgent":
        from .planner_agent import PlannerAgent

        return PlannerAgent
    if name == "ToolAgent":
        from .tool_agent import ToolAgent

        return ToolAgent
    raise AttributeError(name)
