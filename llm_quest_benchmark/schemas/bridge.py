"""Bridge dataclasses for TypeScript integration"""

from dataclasses import dataclass, field


@dataclass
class QMBridgeState:
    """State object returned by TypeScript bridge"""

    location_id: str
    text: str
    choices: list[dict[str, str]]  # [{id: str, text: str}]
    reward: float
    game_ended: bool
    game_state: str = "running"  # "running" | "win" | "fail" | "dead" from TS engine
    params_state: list[str] = field(default_factory=list)
