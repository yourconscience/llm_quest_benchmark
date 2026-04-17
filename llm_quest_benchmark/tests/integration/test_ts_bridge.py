"""Tests for TypeScript bridge"""
import pytest
from unittest.mock import Mock
from pathlib import Path
from llm_quest_benchmark.executors.ts_bridge.bridge import QMBridge
from llm_quest_benchmark.constants import DEFAULT_QUEST


MOCK_PROTOCOL_RESPONSE = {
    "state": {
        "text": "Test observation",
        "choices": [{"jumpId": "1", "text": "Choice 1", "active": True}],
        "gameState": "running",
    },
    "saving": {"locationId": 1},
}

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
    """Test complete game flow with mocked protocol layer."""
    bridge = QMBridge(str(DEFAULT_QUEST))
    try:
        monkeypatch.setattr(bridge, '_read_protocol_message',
                            lambda **kw: (MOCK_PROTOCOL_RESPONSE, []))
        bridge.process = Mock()
        bridge.process.stdin = Mock()
        bridge.process.poll.return_value = None

        state = bridge.start_game()
        assert state.location_id == "1"
        assert state.text == "Test observation"
        assert len(state.choices) == 1
        assert state.choices[0]['id'] == "1"
        assert state.choices[0]['text'] == "Choice 1"
        assert not state.game_ended

        state = bridge.step("1")
        assert state.location_id == "1"
        assert state.text == "Test observation"
        assert len(state.choices) == 1
        assert not state.game_ended

        state = bridge.get_current_state()
        assert state.location_id == "1"
        assert state.text == "Test observation"
        assert len(state.choices) == 1
        assert not state.game_ended
    finally:
        bridge.close()

def test_bridge_error_handling(monkeypatch):
    """Test error handling when protocol layer fails."""
    def mock_read_protocol_message(**kwargs):
        raise RuntimeError("Invalid JSON response from TypeScript bridge")

    bridge = QMBridge(str(DEFAULT_QUEST))
    try:
        monkeypatch.setattr(bridge, '_read_protocol_message', mock_read_protocol_message)
        bridge.process = Mock()
        bridge.process.stderr = Mock()
        bridge.process.stderr.read.return_value = ""
        bridge.process.poll.return_value = None
        with pytest.raises(RuntimeError, match="Failed to start game"):
            bridge.start_game()
    finally:
        bridge.close()

def test_bridge_missing_state(monkeypatch):
    """Test missing state handling."""
    bridge = QMBridge(str(DEFAULT_QUEST))
    try:
        monkeypatch.setattr(bridge, '_read_protocol_message',
                            lambda **kw: ({"state": {}, "saving": {}}, []))
        bridge.process = Mock()
        bridge.process.stderr = Mock()
        bridge.process.stderr.read.return_value = ""
        bridge.process.poll.return_value = None
        with pytest.raises(RuntimeError):
            bridge.start_game()
    finally:
        bridge.close()

def test_bridge_process_cleanup():
    """Test process cleanup"""
    bridge = QMBridge(str(DEFAULT_QUEST))
    bridge.close()  # Should not raise
    assert bridge.process is None


def test_bridge_missing_submodule_dependency(monkeypatch):
    """Bridge should raise actionable error when quest engine sources are missing."""
    monkeypatch.setattr(
        QMBridge,
        "_required_bridge_sources",
        lambda self: [Path("/tmp/definitely-missing-qmreader.ts")],
    )
    with pytest.raises(RuntimeError, match="git submodule update --init --recursive"):
        QMBridge(str(DEFAULT_QUEST))


def test_bridge_parse_response_json_noise():
    """Bridge parser should ignore non-JSON protocol noise lines."""
    bridge = QMBridge(str(DEFAULT_QUEST))
    try:
        assert bridge._parse_response_json("Performing autojump...") is None
        parsed = bridge._parse_response_json('{"state":{"text":"ok","choices":[],"gameState":"running"},"saving":{"locationId":1}}')
        assert isinstance(parsed, dict)
        assert "state" in parsed
        assert "saving" in parsed
    finally:
        bridge.close()
