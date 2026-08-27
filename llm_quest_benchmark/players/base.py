"""Base class for quest players and harnesses."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from llm_quest_benchmark.schemas.records import ProgressState, QuestAction, QuestSnapshot, QuestTransition
from llm_quest_benchmark.schemas.response import LLMResponse


@dataclass
class DecisionContext:
    """Runner-supplied context for one decision.

    ``checkpoints`` is the active-branch checkpoint stack, one-based for the
    harness: index 1 is the first recorded state on the active branch.
    """

    step: int = 0
    checkpoints: list[QuestSnapshot] = field(default_factory=list)
    restore_allowed: bool = False
    restores_remaining: int | None = None
    progress: ProgressState = field(default_factory=ProgressState)


class QuestPlayer(ABC):
    """Abstract base class for quest players"""

    # Only harnesses whose specification declares the choose-or-restore loop may
    # emit restore actions. Everything else can only choose a current option.
    supports_restore: bool = False

    # Canonical harness identifier used to resolve this player's treatment.
    harness_name: str = ""

    def __init__(self, skip_single: bool = False):
        """Initialize player with skip_single option"""
        self.skip_single = skip_single
        self._last_response: LLMResponse = None
        self.agent_id = "base_player"

    def get_action(self, observation: str, choices: list) -> int:
        """Get action number from observation and choices

        Args:
            observation: Current game text
            choices: List of available choices

        Returns:
            Integer containing the choice number (1-based)

        Raises:
            ValueError: If no choices are provided
        """
        if not choices:
            raise ValueError("No choices provided")

        # Handle single choice skipping if enabled
        if self.skip_single and len(choices) == 1:
            self._last_response = LLMResponse(
                action=1,
                reasoning="auto_single_choice",
                is_default=True,
            )
            return 1

        # Implementations that produce richer response metadata replace
        # `_last_response` themselves. Simple players get a fresh response for
        # every decision; never leak a prior auto/default marker forward.
        previous_response = self._last_response
        action = self._get_action_impl(observation, choices)
        if self._last_response is previous_response:
            self._last_response = LLMResponse(action=action)

        return action

    def get_quest_action(
        self,
        observation: str,
        choices: list[dict[str, str]],
        context: DecisionContext,
    ) -> QuestAction:
        """Return the quest action for this decision.

        The default implementation can only choose a current option. The choice
        id and transition timestamp are filled in by the runner, which owns the
        engine mapping.
        """
        index = self.get_action(observation, choices)
        return QuestAction(kind="choose", choice_index=index)

    @abstractmethod
    def _get_action_impl(self, observation: str, choices: list) -> int:
        """Implementation of action selection logic"""
        pass

    def get_last_response(self) -> LLMResponse:
        """Get the last response from the player or harness."""
        return self._last_response

    def on_transition(self, transition: QuestTransition) -> None:
        """Receive one canonical executed transition from the runner."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset player state between episodes"""
        self._last_response = None

    def on_game_start(self) -> None:
        """Called when game starts"""
        self._last_response = None

    def on_game_end(self, final_snapshot: QuestSnapshot | None) -> None:
        """Called when game ends"""
        pass

    def rebuild_from_transitions(self, transitions: list[QuestTransition]) -> None:
        """Rebuild harness memory from a resumed run's recorded transitions."""
        for transition in transitions:
            self.on_transition(transition)

    def __str__(self) -> str:
        """String representation of the player"""
        return self.__class__.__name__

    def describe_state(self) -> dict[str, Any]:
        """Optional harness-specific diagnostics recorded with the run."""
        return {}
