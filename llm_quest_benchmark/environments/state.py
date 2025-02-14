"""State classes for QM environments"""
from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum


class QuestOutcome(str, Enum):
    """Final outcome of a quest execution"""
    SUCCESS = "success"  # Quest completed with positive reward
    FAILURE = "failure"  # Quest completed with negative/zero reward
    ERROR = "error"    # Quest failed to complete (timeout, crash, etc)


@dataclass
class QMState:
    """A QM game state"""
    location_id: str
    text: str
    choices: List[Dict[str, str]]  # [{id: str, text: str}]
    reward: float
    done: bool
    info: Dict[str, Any]