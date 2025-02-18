"""State dataclasses for quest environments"""
from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class QMState:
    """A QM game state"""
    location_id: str
    text: str
    choices: List[Dict[str, str]]  # [{id: str, text: str}]
    reward: float
    done: bool
    info: Dict[str, Any]