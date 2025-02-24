"""Tests for QM environment"""
import pytest
from llm_quest_benchmark.environments.qm import QMPlayerEnv
from llm_quest_benchmark.constants import DEFAULT_QUEST

def test_qm_env_lifecycle():
    """Test QM environment lifecycle - initialization, reset, step, close"""
    env = QMPlayerEnv(str(DEFAULT_QUEST))
    try:
        # Test initialization
        assert env.quest_file == str(DEFAULT_QUEST)
        assert env._current_state == {}

        # Test reset
        observation = env.reset()
        assert isinstance(observation, str)
        assert len(observation) > 0
        state = env.get_state()
        assert 'choices' in state
        assert len(state['choices']) > 0

        # Test step
        observation, done, success, info = env.step("1")
        assert isinstance(observation, str)
        assert isinstance(done, bool)
        assert isinstance(success, bool)
        assert isinstance(info, dict)

    finally:
        env.close()

def test_qm_env_error_handling():
    """Test QM environment error handling"""
    # Test invalid quest file
    with pytest.raises(RuntimeError):
        QMPlayerEnv("nonexistent.qm")

    # Test step without reset
    env = QMPlayerEnv(str(DEFAULT_QUEST))
    try:
        with pytest.raises(RuntimeError):
            env.step("1")
    finally:
        env.close()

    # Test invalid choice
    env = QMPlayerEnv(str(DEFAULT_QUEST))
    try:
        env.reset()
        with pytest.raises(RuntimeError):
            env.step("999")  # Invalid choice number
    finally:
        env.close()