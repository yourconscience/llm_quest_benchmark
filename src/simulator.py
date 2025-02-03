"""
Quest simulation environment with gym-like interface
"""
from typing import Dict, Any, List, Tuple
from .data_structures import QMStructure, QuestState, QMTransition
from .llm_agent import QuestAgent
from pydantic import BaseModel


class StepResult(BaseModel):
    done: bool
    reward: float
    state: QuestState
    transition: QMTransition | None

class QuestSimulator:
    def __init__(self, qm_data: QMStructure, agent: QuestAgent):
        self.qm = qm_data
        self.agent = agent
        self.reset()

    def reset(self) -> QuestState:
        """Reset simulator to initial state"""
        self.state = QuestState(
            current_location=self.qm.locations[self.qm.start_location],
            parameters={p.id: p.initial_value for p in self.qm.parameters.values()},
            history=[],
            valid_transitions=self.state.get_available_transitions(self.qm.transitions)
        )
        return self.state

    def step(self) -> StepResult:
        """Execute one step of the quest"""
        if self.state.current_location.is_terminal:
            return StepResult(
                done=True,
                reward=self.calculate_reward(),
                state=self.state,
                transition=None
            )

        # Get and execute action
        chosen_idx = self.agent.choose_action(
            self.state,
            self.state.valid_transitions
        )
        transition = self.state.valid_transitions[chosen_idx]
        self.state.apply_transition(transition)

        # Update valid transitions
        self.state.valid_transitions = self.state.get_available_transitions(self.qm.transitions)

        return StepResult(
            done=self.state.current_location.is_terminal,
            reward=self.calculate_reward(),
            state=self.state,
            transition=transition
        )

    def calculate_reward(self) -> float:
        # Implementation of calculate_reward method
        pass