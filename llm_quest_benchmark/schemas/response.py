"""Agent dataclasses for LLM interactions"""
from dataclasses import asdict, dataclass
from typing import Optional


@dataclass
class LLMResponse:
    """Structured response from any agent (LLM or not)"""
    action: int  # The chosen action number (1-based) or -1 for tool use
    analysis: Optional[str] = None  # Optional analysis of the choice
    reasoning: Optional[str] = None  # Optional explanation for the choice
    is_default: bool = False  # Whether this is a default value due to parsing error
    tool_type: Optional[str] = None  # Type of tool to use (e.g., "calculator")
    tool_query: Optional[str] = None  # Query for the tool
    tool_result: Optional[str] = None  # Result from the tool execution

    @property
    def is_tool_use(self) -> bool:
        """Check if this response is a tool use request"""
        return self.action == -1 and self.tool_type is not None

    def to_choice_string(self) -> str:
        """Convert to choice string (1-based action number)"""
        if self.is_tool_use:
            return f"Tool: {self.tool_type} - {self.tool_query}"
        return str(self.action)

    def to_dict(self) -> dict:
        """Convert to dict for storage"""
        return {k: v for k, v in asdict(self).items() if v is not None}

    def __str__(self) -> str:
        """Convert to string"""
        if self.is_tool_use:
            return f"Tool: {self.tool_type}\nQuery: {self.tool_query}\nResult: {self.tool_result}"
        if not self.analysis and not self.reasoning:
            return f"Result: {self.action}"
        return f"\nAnalysis: {self.analysis}\nReasoning: {self.reasoning}\nResult: {self.action}"
