"""Basic tests for QM file parsing"""
import pytest
from pathlib import Path
from src.qm import parse_qm, QMGame

@pytest.fixture
def example_quest_path():
    return Path(__file__).parent.parent / "quests" / "boat.qm"

def test_qm_parser_loads_file(example_quest_path):
    """Test that QM parser can load a file"""
    game = parse_qm(str(example_quest_path))
    assert isinstance(game, QMGame)
    assert game.start_id > 0
    assert len(game.locations) > 0

def test_qm_game_basic_navigation(example_quest_path):
    """Test basic game state navigation"""
    game = parse_qm(str(example_quest_path))
    
    # Get starting location
    start_loc = game.get_location(game.start_id)
    assert start_loc.text
    assert len(start_loc.choices) > 0

    # Test choice navigation
    first_choice = start_loc.choices[0]
    next_loc = game.get_location(first_choice.jumpId)
    assert next_loc.text 