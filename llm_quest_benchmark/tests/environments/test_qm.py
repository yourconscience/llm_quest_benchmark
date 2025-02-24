"""Tests for QM environment"""
import pytest
from llm_quest_benchmark.environments.qm import QMPlayerEnv
from llm_quest_benchmark.constants import DEFAULT_QUEST

def test_qm_env_initialization():
    """Test QMPlayerEnv initialization"""
    env = QMPlayerEnv(str(DEFAULT_QUEST))
    assert env.quest_file == str(DEFAULT_QUEST)
    assert env._current_state == {}

def test_qm_env_reset():
    """Test environment reset"""
    env = QMPlayerEnv(str(DEFAULT_QUEST))
    observation = env.reset()
    assert isinstance(observation, str)
    assert len(observation) > 0
    assert env._current_state is not None
    assert 'choices' in env._current_state

def test_qm_env_step():
    """Test environment step"""
    env = QMPlayerEnv(str(DEFAULT_QUEST))
    env.reset()  # Initialize environment
    observation, done, success, info = env.step("1")
    assert isinstance(observation, str)
    assert isinstance(done, bool)
    assert isinstance(success, bool)
    assert isinstance(info, dict)

def test_qm_env_state_property():
    """Test state property"""
    env = QMPlayerEnv(str(DEFAULT_QUEST))
    assert env.state == {}  # Empty before reset
    env.reset()
    assert isinstance(env.state, dict)
    assert 'choices' in env.state