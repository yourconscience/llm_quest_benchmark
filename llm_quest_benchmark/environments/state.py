"""State classes for QM environments"""
from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class QMState:
    """A QM game state"""
    location_id: str
    text: str
    choices: List[Dict[str, str]]  # [{id: str, text: str}]
    reward: float
    done: bool
    info: Dict[str, Any]