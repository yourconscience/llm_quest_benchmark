"""Example to test the QMPlayer environment integration."""

import os
import pytest

from llm_quest_benchmark.environments.qm import SimpleQMEnv
from llm_quest_benchmark.agents.simple_agent import SimpleQuestAgent

def test_qm_env_e2e():
    """Test end-to-end interaction with QM environment."""
    # Initialize environment
    env = SimpleQMEnv(quest_file="quests/boat.qm")
    agent = SimpleQuestAgent(model="gpt-4o")

    # Reset environment
    state = env.reset()
    assert state is not None
    assert "text" in state
    assert "choices" in state
    assert len(state["choices"]) > 0

    # Take a step
    action = agent.step(state)
    assert isinstance(action, int)
    assert 0 <= action < len(state["choices"])

    # Step environment
    next_state, reward, done, info = env.step(action)
    assert next_state is not None
    assert isinstance(reward, (int, float))
    assert isinstance(done, bool)
    assert isinstance(info, dict)

    # Clean up
    env.close()
