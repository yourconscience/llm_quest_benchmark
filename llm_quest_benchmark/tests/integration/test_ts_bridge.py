"""Integration tests for TypeScript bridge"""
import pytest
from pathlib import Path
import json
from unittest.mock import patch, MagicMock

from llm_quest_benchmark.executors.ts_bridge.bridge import TypeScriptBridge
from llm_quest_benchmark.constants import DEFAULT_QUEST

@pytest.fixture
def mock_subprocess():
    """Mock subprocess for TypeScript bridge"""
    with patch('subprocess.Popen') as mock_popen:
        # Mock the process
        process_mock = MagicMock()
        process_mock.stdout.readline.return_value = json.dumps({
            "type": "init",
            "data": {
                "location_id": "start",
                "observation": "You are in a boat.",
                "choices": [
                    {"id": "1", "text": "Go north"}
                ]
            }
        }).encode()
        process_mock.poll.return_value = None  # Process is running
        mock_popen.return_value = process_mock
        yield mock_popen

@pytest.fixture
def bridge(mock_subprocess, test_logger):
    """Create TypeScript bridge instance with mocked subprocess"""
    bridge = TypeScriptBridge(DEFAULT_QUEST, test_logger)
    yield bridge
    bridge.close()

def test_bridge_initialization(bridge, mock_subprocess):
    """Test that bridge initializes correctly"""
    assert bridge.quest_path == DEFAULT_QUEST
    mock_subprocess.assert_called_once()
    cmd_args = mock_subprocess.call_args[0][0]
    assert "node" in cmd_args[0]
    assert "ts-node" in cmd_args[1]
    assert str(DEFAULT_QUEST) in cmd_args[-1]

def test_bridge_start_game(bridge):
    """Test starting a game through the bridge"""
    state = bridge.start_game()
    assert state is not None
    assert state.location_id == "start"
    assert state.observation == "You are in a boat."
    assert len(state.choices) == 1
    assert state.choices[0].text == "Go north"

def test_bridge_make_choice(bridge):
    """Test making a choice through the bridge"""
    # First start the game
    bridge.start_game()

    # Mock the next response for make_choice
    bridge.process.stdout.readline.return_value = json.dumps({
        "type": "state",
        "data": {
            "location_id": "end_success",
            "observation": "You made it!",
            "choices": []
        }
    }).encode()

    state = bridge.make_choice("1")
    assert state is not None
    assert state.location_id == "end_success"
    assert state.observation == "You made it!"
    assert len(state.choices) == 0

def test_bridge_error_handling(mock_subprocess, test_logger):
    """Test bridge error handling for invalid responses"""
    # Mock invalid JSON response
    mock_subprocess.return_value.stdout.readline.return_value = b"invalid json"

    bridge = TypeScriptBridge(DEFAULT_QUEST, test_logger)
    with pytest.raises(RuntimeError, match="Failed to parse JSON"):
        bridge.start_game()

def test_bridge_missing_state(mock_subprocess, test_logger):
    """Test bridge handling when no state is received"""
    # Mock empty response
    mock_subprocess.return_value.stdout.readline.return_value = b""

    bridge = TypeScriptBridge(DEFAULT_QUEST, test_logger)
    with pytest.raises(RuntimeError, match="No initial state received"):
        bridge.start_game()

def test_bridge_process_termination(bridge):
    """Test bridge handling when process terminates"""
    # Mock process termination
    bridge.process.poll.return_value = 1

    with pytest.raises(RuntimeError, match="Bridge process terminated"):
        bridge.make_choice("1")