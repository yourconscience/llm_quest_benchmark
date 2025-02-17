"""State classes for QM environments"""
from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum


class QuestOutcome(Enum):
    """Possible quest outcomes"""
    SUCCESS = "success"  # Quest completed successfully
    FAILURE = "failure"  # Quest completed but goal not achieved
    ERROR = "error"  # Quest failed due to technical error or timeout

    @property
    def exit_code(self) -> int:
        """Get the exit code for this outcome"""
        if self in [QuestOutcome.SUCCESS, QuestOutcome.FAILURE]:
            return 0  # Both success and failure are valid outcomes
        return 2  # Error outcomes return 2


@dataclass
class QMState:
    """A QM game state"""
    location_id: str
    text: str
    choices: List[Dict[str, str]]  # [{id: str, text: str}]
    reward: float
    done: bool
    info: Dict[str, Any]