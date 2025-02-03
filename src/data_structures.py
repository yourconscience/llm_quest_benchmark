"""
QM data structures and game state representation
"""
from pydantic import BaseModel
from typing import Dict, List, Tuple
from enum import Enum

class QMParameterType(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    DEATH = "death"

class QMParameter(BaseModel):
    id: int
    name: str
    min_value: int
    max_value: int
    initial_value: int
    is_money: bool = False
    critical_type: QMParameterType | None = None

class QMLocation(BaseModel):
    id: int
    descriptions: List[str]
    is_terminal: bool
    parameter_mods: Dict[int, int]
    days_consumed: int = 0

class QMTransition(BaseModel):
    source: int
    target: int
    description: str
    conditions: Dict[int, Tuple[int, int]]  # param_id: (min, max)
    priority: float = 1.0
    max_uses: int = 0

    def is_available(self, params: Dict[int, int]) -> bool:
        """Check if transition is available given current parameters"""
        return all(
            params[param_id] >= min_val
            and params[param_id] <= max_val
            for param_id, (min_val, max_val) in self.conditions.items()
        )

class QMStructure(BaseModel):
    parameters: Dict[int, QMParameter]
    locations: Dict[int, QMLocation]
    transitions: List[QMTransition]
    start_location: int

class QuestState(BaseModel):
    current_location: QMLocation
    parameters: Dict[int, int]
    history: List[Dict]
    days_passed: int = 0
    valid_transitions: List[QMTransition]

    def get_available_transitions(self, all_transitions: List[QMTransition]) -> List[QMTransition]:
        """Get valid transitions from current location"""
        return [
            t for t in all_transitions
            if t.source == self.current_location.id
            and t.is_available(self.parameters)
        ]

    def apply_transition(self, transition: QMTransition) -> None:
        """Update state based on chosen transition"""
        # Update parameters
        for param_id, change in transition.parameter_mods.items():
            self.parameters[param_id] += change

        # Update location
        self.current_location = transition.target
        self.days_passed += transition.days_consumed
        self.history.append({
            "location": transition.source,
            "action": transition.description,
            "params": self.parameters.copy()
        })