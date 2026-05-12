__all__ = ["QuestPlayer", "HumanPlayer", "RandomAgent"]


def __getattr__(name):
    if name == "QuestPlayer":
        from .base import QuestPlayer

        return QuestPlayer
    if name == "HumanPlayer":
        from .human_player import HumanPlayer

        return HumanPlayer
    if name == "RandomAgent":
        from .random_agent import RandomAgent

        return RandomAgent
    raise AttributeError(name)
