"""Null renderer that does nothing - used for debug mode and when no rendering is needed"""
from typing import Dict, Any
from llm_quest_benchmark.renderers.base import BaseRenderer


class NoRenderer(BaseRenderer):
    """Null renderer implementation that does nothing"""

    def render_game_state(self, state: Dict[str, Any]) -> None:
        """Do nothing implementation of game state rendering"""
        pass

    def render_title(self) -> None:
        """Do nothing implementation of title rendering"""
        pass

    def render_quest_text(self, text: str) -> None:
        """Do nothing implementation of quest text rendering"""
        pass

    def render_choices(self, choices: list) -> None:
        """Do nothing implementation of choices rendering"""
        pass

    def render_parameters(self, params: list) -> None:
        """Do nothing implementation of parameters rendering"""
        pass

    def render_error(self, message: str) -> None:
        """Do nothing implementation of error rendering"""
        pass

    def close(self) -> None:
        """Do nothing implementation of cleanup"""
        pass