"""Agent dataclasses for LLM interactions"""
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class LLMResponse:
    """Structured response from any agent (LLM or not)"""
    action: int  # The chosen action number (1-based)
    analysis: Optional[str] = None  # Optional analysis of the choice
    reasoning: Optional[str] = None  # Optional explanation for the choice
    is_default: bool = False  # Whether this is a default value due to parsing error
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None

    def to_choice_string(self) -> str:
        """Convert to choice string (1-based action number)"""
        return str(self.action)

    def to_dict(self) -> dict:
        """Convert to dict for storage"""
        return {k: v for k, v in asdict(self).items() if v is not None}

    def __str__(self) -> str:
        """Convert to string"""
        if not self.analysis and not self.reasoning:
            return f"Result: {self.action}"
        return f"\nAnalysis: {self.analysis}\nReasoning: {self.reasoning}\nResult: {self.action}"
