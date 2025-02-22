"""Tests for QM environment"""
import pytest
from unittest.mock import Mock, patch

from llm_quest_benchmark.environments.qm import QMPlayerEnv
from llm_quest_benchmark.dataclasses.bridge import QMBridgeState


@pytest.fixture
def mock_bridge_state():
    """Create a mock bridge state"""
    return QMBridgeState(
        location_id="1",
        text="You are in a room",
        choices=[{"id": "1", "text": "Go north"}, {"id": "2", "text": "Go south"}],
        reward=0.0,
        game_ended=False
    )


@pytest.fixture
def mock_bridge(mock_bridge_state):
    """Create a mock QMBridge"""
    mock = Mock()
    mock.start_game.return_value = mock_bridge_state
    mock.step.return_value = mock_bridge_state
    return mock


def test_qm_env_initialization():
    """Test QMPlayerEnv initialization"""
    env = QMPlayerEnv("test.qm", debug=True)
    assert env.quest_file == "test.qm"
    assert env.debug is True
    assert env._current_state == {}


def test_qm_env_reset(mock_bridge, mock_bridge_state):
    """Test environment reset"""
    env = QMPlayerEnv("test.qm")
    env.bridge = mock_bridge

    # Test reset
    observation = env.reset()
    assert observation == mock_bridge_state.text
    assert env._current_state['location_id'] == mock_bridge_state.location_id
    assert env._current_state['text'] == mock_bridge_state.text
    assert env._current_state['choices'] == mock_bridge_state.choices
    assert env._current_state['done'] == mock_bridge_state.game_ended


def test_qm_env_step(mock_bridge, mock_bridge_state):
    """Test environment step"""
    env = QMPlayerEnv("test.qm")
    env.bridge = mock_bridge

    # Set up winning state
    winning_state = QMBridgeState(
        location_id="2",
        text="You won!",
        choices=[],
        reward=1.0,
        game_ended=True
    )
    mock_bridge.step.return_value = winning_state

    # Take step
    observation, done, success, info = env.step("1")
    assert observation == winning_state.text
    assert done is True
    assert success is True  # Should be True because game_ended and reward > 0
    assert isinstance(info, dict)


def test_qm_env_state_property():
    """Test state property"""
    env = QMPlayerEnv("test.qm")

    # Test empty state
    assert env.state == {}

    # Test with state
    test_state = {
        'location_id': '1',
        'text': 'test',
        'choices': [],
        'done': False,
        'info': {}
    }
    env._current_state = test_state.copy()
    assert env.state == test_state

    # Verify state is copied
    state = env.state
    state['new_key'] = 'value'
    assert 'new_key' not in env.state


def test_qm_env_format_observation():
    """Test observation formatting"""
    env = QMPlayerEnv("test.qm")
    state = {
        'text': 'Test text',
        'choices': [{'text': 'Choice 1'}, {'text': 'Choice 2'}]
    }
    formatted = env._format_observation(Mock(**state))
    assert 'Test text' in formatted
    assert '1. Choice 1' in formatted
    assert '2. Choice 2' in formatted


def test_qm_env_cleanup():
    """Test environment cleanup"""
    env = QMPlayerEnv("test.qm")
    mock_bridge = Mock()
    env.bridge = mock_bridge
    env.close()
    mock_bridge.close.assert_called_once()