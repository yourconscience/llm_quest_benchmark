"""Agent dataclasses for LLM interactions"""

from dataclasses import asdict, dataclass


@dataclass
class LLMResponse:
    """Structured response from any agent (LLM or not)"""

    action: int  # The chosen action number (1-based)
    analysis: str | None = None  # Optional analysis of the choice
    reasoning: str | None = None  # Optional explanation for the choice
    memo: str | None = None  # State tracking: inventory, health, codes, quest phase
    tool_calls: list[dict] | None = None  # Tool calls requested by tool-augmented agents
    tool_results: list[str] | None = None  # Tool outputs returned to the model
    is_default: bool = False  # Whether this is a default value due to parsing error
    parse_mode: str | None = None  # How the output was parsed (json/number/default/etc)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None

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
