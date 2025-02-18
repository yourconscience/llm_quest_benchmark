"""Strategic agent decorator that adds analysis capabilities"""
import logging
from typing import Dict, Any

from llm_quest_benchmark.agents.base import QuestPlayer
from llm_quest_benchmark.renderers.prompt_renderer import PromptRenderer
from llm_quest_benchmark.constants import DEFAULT_TEMPLATE


class StrategicAgent(QuestPlayer):
    """Decorator that adds strategic thinking to any quest player"""

    def __init__(self, base_agent: QuestPlayer, debug: bool = False, template: str = "advanced.jinja"):
        """Initialize strategic agent wrapper

        Args:
            base_agent: Base agent to wrap (usually LLMAgent)
            debug: Enable debug logging
            template: Template to use for enhanced prompts
        """
        super().__init__(skip_single=base_agent.skip_single)
        self.agent = base_agent
        self.debug = debug
        self.history = []

        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        if self.debug:
            self.logger.setLevel(logging.DEBUG)
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(name)s - %(message)s'))
            self.logger.addHandler(handler)

        # Initialize prompt renderer
        self.prompt_renderer = PromptRenderer(None, template=template)

    def _get_action_impl(self, observation: str, choices: list) -> str:
        """Implementation of action selection logic with strategic analysis"""
        if hasattr(self.agent, 'llm'):
            # First, get situation analysis
            if self.debug:
                self.logger.debug(f"\nObservation:\n{observation}")

            analysis = self.agent.llm(
                "Analyze this situation and explain your thinking step-by-step instead of choosing an action:\n"
                + observation)

            if self.debug:
                self.logger.debug(f"\nAnalysis:\n{analysis}")

            # Store analysis in history
            self.history.append({
                'observation': observation,
                'analysis': analysis
            })

            # Get enhanced context with history
            enhanced_context = self.get_enhanced_context(observation, choices)
            if self.debug:
                self.logger.debug(f"\nEnhanced Context:\n{enhanced_context}")

            # Then make the actual choice with analysis context
            return self.agent.get_action(enhanced_context, choices)
        else:
            # If agent doesn't have LLM capability, just pass through
            return self.agent.get_action(observation, choices)

    def get_enhanced_context(self, observation: str, choices: list) -> str:
        """Build context for advanced prompt with historical analysis"""
        context = [
            f"Turn {len(self.history)+1}: {entry['analysis']}"
            for entry in self.history[-3:]  # Last 3 analyses
        ]
        return self.prompt_renderer.render_action_prompt(
            observation=observation,
            choices=choices,
            state_tracker=context
        )

    def reset(self) -> None:
        """Reset both strategic and base agent state"""
        self.history = []
        self.agent.reset()

    def on_game_start(self) -> None:
        """Pass through to base agent"""
        if self.debug:
            self.logger.debug("Starting new game with strategic analysis")
        self.agent.on_game_start()

    def on_game_end(self, final_state: Dict[str, Any]) -> None:
        """Pass through to base agent and log analysis history"""
        self.agent.on_game_end(final_state)
        if self.debug:
            self.logger.debug("Final Analysis History:")
            for entry in self.history:
                self.logger.debug(f"\nObservation: {entry['observation']}")
                self.logger.debug(f"Analysis: {entry['analysis']}")