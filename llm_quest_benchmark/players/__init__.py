__all__ = ["QuestPlayer", "HumanPlayer", "RandomPlayer"]


def __getattr__(name):
    if name == "QuestPlayer":
        from .base import QuestPlayer

        return QuestPlayer
    if name == "HumanPlayer":
        from .human import HumanPlayer

        return HumanPlayer
    if name == "RandomPlayer":
        from .random import RandomPlayer

        return RandomPlayer
    raise AttributeError(name)
