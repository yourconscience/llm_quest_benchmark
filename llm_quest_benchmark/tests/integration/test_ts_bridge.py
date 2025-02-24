"""Tests for TypeScript bridge"""
import pytest
from pathlib import Path
from llm_quest_benchmark.executors.ts_bridge.bridge import QMBridge
from llm_quest_benchmark.constants import DEFAULT_QUEST

def test_bridge_initialization():
    """Test bridge initialization"""
    bridge = QMBridge(str(DEFAULT_QUEST))
    assert bridge.quest_file == Path(DEFAULT_QUEST).resolve()
    assert not bridge.debug
    assert bridge.process is None

def test_bridge_parse_quest():
    """Test quest parsing"""
    bridge = QMBridge(str(DEFAULT_QUEST))
    metadata = bridge.parse_quest_locations()
    assert isinstance(metadata, dict)
    assert 'locations' in metadata
    assert 'start_location_id' in metadata
    assert isinstance(metadata['start_location_id'], int)
    assert metadata['start_location_id'] > 0

def test_bridge_invalid_quest():
    """Test bridge with invalid quest file"""
    with pytest.raises(FileNotFoundError):
        QMBridge('nonexistent.qm')

def test_bridge_start_game(monkeypatch):
    """Test game start"""
    def mock_read_response(*args, **kwargs):
        return '''{
            "state": {
                "text": "Test",
                "choices": [{"jumpId": "1", "text": "Choice 1", "active": true}],
                "gameState": "running"
            },
            "saving": {
                "locationId": 1
            }
        }'''

    bridge = QMBridge(str(DEFAULT_QUEST))
    monkeypatch.setattr(bridge, '_read_response', mock_read_response)
    state = bridge.start_game()
    assert state.location_id == "1"
    assert state.text == "Test"
    assert len(state.choices) == 1
    assert state.choices[0]['id'] == "1"
    assert state.choices[0]['text'] == "Choice 1"
    assert not state.game_ended

def test_bridge_make_choice(monkeypatch):
    """Test making a choice"""
    def mock_read_response(*args, **kwargs):
        return '''{
            "state": {
                "text": "Choice made",
                "choices": [{"jumpId": "2", "text": "Choice 2", "active": true}],
                "gameState": "running"
            },
            "saving": {
                "locationId": 2
            }
        }'''

    bridge = QMBridge(str(DEFAULT_QUEST))
    monkeypatch.setattr(bridge, '_read_response', mock_read_response)
    bridge.start_game()
    state = bridge.step("1")
    assert state.location_id == "2"
    assert state.text == "Choice made"
    assert len(state.choices) == 1
    assert state.choices[0]['id'] == "2"
    assert state.choices[0]['text'] == "Choice 2"
    assert not state.game_ended

def test_bridge_error_handling(monkeypatch):
    """Test error handling"""
    def mock_read_response(*args, **kwargs):
        return 'invalid json'

    bridge = QMBridge(str(DEFAULT_QUEST))
    monkeypatch.setattr(bridge, '_read_response', mock_read_response)
    with pytest.raises(RuntimeError, match="Invalid JSON response from TypeScript bridge"):
        bridge.start_game()

def test_bridge_missing_state(monkeypatch):
    """Test missing state handling"""
    def mock_read_response(*args, **kwargs):
        return ''

    bridge = QMBridge(str(DEFAULT_QUEST))
    monkeypatch.setattr(bridge, '_read_response', mock_read_response)
    with pytest.raises(RuntimeError, match="No initial state received"):
        bridge.start_game()

def test_bridge_process_termination(monkeypatch):
    """Test process termination handling"""
    bridge = QMBridge(str(DEFAULT_QUEST))
    bridge.process = None  # Simulate process not started
    with pytest.raises(RuntimeError, match="Game process not started"):
        bridge._read_response()