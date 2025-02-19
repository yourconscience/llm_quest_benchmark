"""Agent dataclasses for LLM interactions"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMResponse:
    """Structured response from LLM agent"""
    action: int  # The chosen action number (1-based)
    reasoning: Optional[str] = None  # Optional explanation for the choice
    is_default: bool = False  # Whether this is a default value due to parsing error

    def to_choice_string(self) -> str:
        """Convert to choice string (1-based action number)"""
        return str(self.action)
