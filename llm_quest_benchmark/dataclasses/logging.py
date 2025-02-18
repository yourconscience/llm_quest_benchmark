"""Logging dataclasses for quest execution"""
from dataclasses import dataclass
from typing import Dict, Any, Optional
from datetime import datetime


@dataclass
class QuestStep:
    """Single step in quest execution"""
    step: int
    state: str
    choices: list
    prompt: str
    response: str
    reward: float = 0.0
    metrics: Dict[str, Any] = None
    timestamp: str = ""
    llm_response: Optional[Dict[str, Any]] = None  # Store full LLM response including reasoning

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_console_line(self, is_llm: bool = False) -> str:
        """Format step for console output based on player type"""
        if is_llm:
            base_line = f"Step {self.step} | Action: {self.response} | Reward: {self.reward} | Choices: {len(self.choices)}"
            if isinstance(self.llm_response, dict) and "reasoning" in self.llm_response and self.llm_response["reasoning"]:
                reasoning_text = str(self.llm_response["reasoning"])
                return f"{base_line}\n    Reasoning: {reasoning_text}"
            return base_line
        else:
            # For human players, just show the state and choices
            return f"Step {self.step} | Choices: {len(self.choices)}"

    def to_json(self) -> Dict[str, Any]:
        """Convert step to JSON format for analysis"""
        return {
            "step": self.step,
            "timestamp": self.timestamp,
            "state": self.state,
            "choices": self.choices,
            "prompt": self.prompt,
            "response": self.response,
            "reward": self.reward,
            "metrics": self.metrics or {},
            "llm_response": self.llm_response
        }