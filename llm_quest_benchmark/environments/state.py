"""State definitions for quest environments"""
from enum import Enum


class QuestOutcome(Enum):
    """Possible quest outcomes"""
    SUCCESS = 1
    FAILURE = 0
    ERROR = -1

    @property
    def is_error(self) -> bool:
        """Whether this outcome represents an error state"""
        return self == QuestOutcome.ERROR

    @property
    def exit_code(self) -> int:
        """Get the appropriate exit code for this outcome.
        Normal outcomes (SUCCESS, FAILURE) return 0
        while ERROR always returns 2 (standard Unix error code)"""
        return 2 if self.is_error else 0