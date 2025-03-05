"""Tests for TypeScript bridge"""
import pytest
from pathlib import Path
from llm_quest_benchmark.executors.ts_bridge.bridge import QMBridge
from llm_quest_benchmark.constants import DEFAULT_QUEST

def test_bridge_initialization():
    """Test bridge initialization"""
    bridge = QMBridge(str(DEFAULT_QUEST))
    try:
        assert bridge.quest_file == Path(DEFAULT_QUEST).resolve()
        assert not bridge.debug
        assert bridge.process is None
    finally:
        bridge.close()

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

def test_bridge_game_flow(monkeypatch):
    """Test complete game flow"""
    def mock_read_response(*args, **kwargs):
        return '''{
            "state": {
                "text": "Test observation",
                "choices": [{"jumpId": "1", "text": "Choice 1", "active": true}],
                "gameState": "running"
            },
            "saving": {
                "locationId": 1
            }
        }'''

    bridge = QMBridge(str(DEFAULT_QUEST))
    try:
        monkeypatch.setattr(bridge, '_read_response', mock_read_response)

        # Test start game
        state = bridge.start_game()
        assert state.location_id == "1"
        assert state.text == "Test observation"
        assert len(state.choices) == 1
        assert state.choices[0]['id'] == "1"
        assert state.choices[0]['text'] == "Choice 1"
        assert not state.game_ended

        # Test make choice
        state = bridge.step("1")
        assert state.location_id == "1"
        assert state.text == "Test observation"
        assert len(state.choices) == 1
        assert not state.game_ended

        # Test get current state
        state = bridge.get_current_state()
        assert state.location_id == "1"
        assert state.text == "Test observation"
        assert len(state.choices) == 1
        assert not state.game_ended
    finally:
        bridge.close()

def test_bridge_error_handling(monkeypatch):
    """Test error handling"""
    def mock_read_response(*args, **kwargs):
        return 'invalid json'

    bridge = QMBridge(str(DEFAULT_QUEST))
    try:
        monkeypatch.setattr(bridge, '_read_response', mock_read_response)
        with pytest.raises(RuntimeError):
            bridge.start_game()
    finally:
        bridge.close()

def test_bridge_missing_state(monkeypatch):
    """Test missing state handling"""
    def mock_read_response(*args, **kwargs):
        return '''{
            "state": {},
            "saving": {}
        }'''

    bridge = QMBridge(str(DEFAULT_QUEST))
    try:
        monkeypatch.setattr(bridge, '_read_response', mock_read_response)
        with pytest.raises(RuntimeError):
            bridge.start_game()
    finally:
        bridge.close()

def test_bridge_process_cleanup():
    """Test process cleanup"""
    bridge = QMBridge(str(DEFAULT_QUEST))
    bridge.close()  # Should not raise
    assert bridge.process is None