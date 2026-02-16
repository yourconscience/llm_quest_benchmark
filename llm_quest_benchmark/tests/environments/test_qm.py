"""Tests for QM environment"""
import logging
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


class _FakeBridgeState:
    def __init__(self, text: str):
        self.text = text


class _FakeBridge:
    def __init__(self, states):
        self.state_history = states

    def step(self, _action):
        raise AssertionError("step() should not be called when loop detection triggers")


def test_infinite_loop_detection_sets_terminal_failure_state():
    """Loop guard must produce a terminal env state, not a dangling non-final snapshot."""
    env = QMPlayerEnv.__new__(QMPlayerEnv)
    env.debug = False
    env.language = "rus"
    env.logger = logging.getLogger("test_qm_loop_guard")
    env.bridge = _FakeBridge([_FakeBridgeState("Наступил новый день") for _ in range(31)])
    env._current_state = {
        "location_id": "1",
        "text": "Наступил новый день",
        "params_state": ["День: 10"],
        "choices": [{"id": "1", "text": "Ждать"}],
        "reward": 0.0,
        "done": False,
        "info": {},
    }

    observation, done, success, info = env.step("1")

    assert done is True
    assert success is False
    assert info["forced_completion"] is True
    assert env.state["done"] is True
    assert env.state["choices"] == []
    assert "Forced stop" in observation

    # Test invalid choice
    env = QMPlayerEnv(str(DEFAULT_QUEST))
    try:
        env.reset()
        with pytest.raises(RuntimeError):
            env.step("999")  # Invalid choice number
    finally:
        env.close()
