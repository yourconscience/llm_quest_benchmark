"""State dataclasses for quest environments"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from .response import LLMResponse


@dataclass
class QMState:
    """A QM game state"""
    location_id: str
    text: str
    choices: List[Dict[str, str]]  # [{id: str, text: str}]
    reward: float
    done: bool
    info: Dict[str, Any]


@dataclass
class AgentState:
    """State for tracking agent interactions with quest"""
    step: int  # Current step number
    location_id: str  # Current location in quest
    observation: str  # Current game text/observation
    choices: List[Dict[str, str]]  # Available choices
    action: str  # Agent's chosen action (e.g. "1" or "Go north")
    llm_response: LLMResponse  # Agent's response (LLM or not)

    @classmethod
    def from_qm_state(cls, qm_state: QMState, step: int, action: str, llm_response: LLMResponse) -> 'AgentState':
        """Create AgentState from QMState and agent response"""
        return cls(
            step=step,
            location_id=qm_state.location_id,
            observation=qm_state.text,
            choices=qm_state.choices,
            action=action,
            llm_response=llm_response
        )

    def __str__(self) -> str:
        """String representation of AgentState"""
        choices_str = "\n".join([f"{i+1}. {choice['text']}" for i, choice in enumerate(self.choices)])
        return f"Step {self.step}.\nObservation: {self.observation}.\nChoices:\n{choices_str}\nLLM Response:\n{str(self.llm_response)}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert AgentState to dictionary"""
        return {
            'step': self.step,
            'location_id': self.location_id,
            'observation': self.observation,
            'choices': self.choices,
            'action': self.action,
            'llm_response': self.llm_response.to_dict() if self.llm_response else None,
            'game_ended': False  # Default value, can be updated by caller
        }
