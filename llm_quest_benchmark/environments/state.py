"""State definitions for quest environments"""
from enum import Enum


class QuestOutcome(Enum):
    """Possible quest outcomes"""
    SUCCESS = 1
    FAILURE = 0
    ERROR = -1
    TIMEOUT = -2  # Add timeout state

    @property
    def is_error(self) -> bool:
        """Whether this outcome represents an error state"""
        return self in (QuestOutcome.ERROR, QuestOutcome.TIMEOUT)

    @property
    def exit_code(self) -> int:
        """Get the appropriate exit code for this outcome.
        Normal outcomes (SUCCESS, FAILURE) return 0,
        TIMEOUT returns 124 (standard Unix timeout code),
        ERROR returns 2 (standard Unix error code)"""
        if self == QuestOutcome.TIMEOUT:
            return 124  # Standard Unix timeout exit code
        return 2 if self.is_error else 0