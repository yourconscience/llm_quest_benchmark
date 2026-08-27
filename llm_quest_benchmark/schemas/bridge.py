"""Bridge dataclasses for TypeScript integration"""

from dataclasses import dataclass, field
from typing import Any

from llm_quest_benchmark.schemas.records import QuestSnapshot


@dataclass
class QMBridgeState:
    """State object returned by TypeScript bridge.

    ``saving`` is the full engine ``GameState`` (including its PRNG state), which
    is what makes exact restore and deterministic replay possible.
    """

    location_id: str
    text: str
    choices: list[dict[str, str]]  # [{id: str, text: str}]
    reward: float
    game_ended: bool
    game_state: str = "running"  # "running" | "win" | "fail" | "dead" from TS engine
    params_state: list[str] = field(default_factory=list)
    saving: dict[str, Any] = field(default_factory=dict)

    def to_snapshot(self) -> QuestSnapshot:
        """Convert to the canonical snapshot used by records and replay."""
        return QuestSnapshot(
            location_id=str(self.location_id),
            observation=self.text,
            choices=[{"id": str(c["id"]), "text": c["text"]} for c in self.choices],
            params_state=list(self.params_state),
            reward=self.reward,
            done=self.game_ended,
            game_state=self.game_state,
            saving=self.saving or None,
        )
