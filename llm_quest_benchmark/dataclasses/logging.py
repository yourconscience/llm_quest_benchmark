"""Logging dataclasses for quest execution"""
from dataclasses import dataclass
from typing import Dict, Any, Optional
from datetime import datetime


@dataclass
class QuestStep:
    """Single step in quest execution"""
    step: int
    state: str # current state of the game
    choices: list # available choices
    response: str # single choice response
    metrics: Dict[str, Any] = None
    timestamp: str = ""
    reward: float = 0.0
    llm_response: Optional[Dict[str, Any]] = None  # Store full LLM response including reasoning

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_console_line(self) -> str:
        """Format step for console output based on player type"""
        choices_str = "\n".join([f"{i}: {choice}" for i, choice in enumerate(self.choices, 1)])
        if self.llm_response:
            base_line = f"Step {self.step} | Action: {self.response} | Choices:\n{choices_str}"
            if isinstance(self.llm_response, dict) and "reasoning" in self.llm_response and self.llm_response["reasoning"]:
                reasoning_text = str(self.llm_response["reasoning"])
                return f"{base_line}\n    Reasoning: {reasoning_text}"
            return base_line
        else:
            # For human players, just show the state and choices
            return f"Step {self.step} | Choices:\n{choices_str}"

    def to_json(self) -> Dict[str, Any]:
        """Convert step to JSON format for analysis"""
        return {
            "step": self.step,
            "timestamp": self.timestamp,
            "state": self.state,
            "choices": self.choices,
            "response": self.response,
            "reward": self.reward,
            "metrics": self.metrics or {},
            "llm_response": self.llm_response
        }