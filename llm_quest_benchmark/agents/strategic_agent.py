"""Deprecated compatibility wrapper for strategic agents."""

import logging
import warnings
from typing import Any

from llm_quest_benchmark.agents.base import QuestPlayer
from llm_quest_benchmark.llm.prompt import PromptRenderer

warnings.warn("strategic_agent is deprecated, use llm_quest_benchmark.harnesses", DeprecationWarning, stacklevel=2)


class StrategicAgent(QuestPlayer):
    """Backward-compatible strategic analysis decorator."""

    def __init__(self, base_agent: QuestPlayer, debug: bool = False, template: str = "advanced.jinja"):
        super().__init__(skip_single=base_agent.skip_single)
        self.agent = base_agent
        self.debug = debug
        self.history = []

        self.logger = logging.getLogger(self.__class__.__name__)
        if self.debug:
            self.logger.setLevel(logging.DEBUG)
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(name)s - %(message)s"))
            self.logger.addHandler(handler)

        self.prompt_renderer = PromptRenderer(None, template=template)

    def _get_action_impl(self, observation: str, choices: list) -> int:
        if hasattr(self.agent, "llm"):
            if self.debug:
                self.logger.debug("\nObservation:\n%s", observation)

            analysis = self.agent.llm(
                "Analyze this situation and explain your thinking step-by-step instead of choosing an action:\n"
                + observation
            )

            if self.debug:
                self.logger.debug("\nAnalysis:\n%s", analysis)

            self.history.append({"observation": observation, "analysis": analysis})
            enhanced_context = self.get_enhanced_context(observation, choices)
            if self.debug:
                self.logger.debug("\nEnhanced Context:\n%s", enhanced_context)

            return self.agent.get_action(enhanced_context, choices)

        return self.agent.get_action(observation, choices)

    def get_enhanced_context(self, observation: str, choices: list) -> str:
        context = [f"Turn {len(self.history) + 1}: {entry['analysis']}" for entry in self.history[-3:]]
        return self.prompt_renderer.render_action_prompt(
            observation=observation,
            choices=choices,
            state_tracker=context,
        )

    def reset(self) -> None:
        self.history = []
        self.agent.reset()

    def on_game_start(self) -> None:
        if self.debug:
            self.logger.debug("Starting new game with strategic analysis")
        self.agent.on_game_start()

    def on_game_end(self, final_state: dict[str, Any]) -> None:
        self.agent.on_game_end(final_state)
        if self.debug:
            self.logger.debug("Final Analysis History:")
            for entry in self.history:
                self.logger.debug("\nObservation: %s", entry["observation"])
                self.logger.debug("Analysis: %s", entry["analysis"])


__all__ = ["StrategicAgent"]
