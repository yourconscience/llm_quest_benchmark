"""Bridge dataclasses for TypeScript integration"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any


@dataclass
class QMBridgeState:
    """State object returned by TypeScript bridge"""
    location_id: str
    text: str
    choices: List[Dict[str, str]]  # [{id: str, text: str}]
    reward: float
    game_ended: bool
    params_state: List[str] = field(default_factory=list)
