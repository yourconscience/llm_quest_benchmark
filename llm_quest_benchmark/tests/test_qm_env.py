"""Basic tests for QM file parsing"""

from llm_quest_benchmark.environments.qm import parse_qm, QMGame
from llm_quest_benchmark.constants import DEFAULT_QUEST

def test_qm_file_exists():
    """Test that test quest file exists"""
    assert DEFAULT_QUEST.exists(), f"Test quest file not found: {DEFAULT_QUEST}"

def test_qm_parser_loads_file():
    """Test that QM parser can load a file"""
    game = parse_qm(str(DEFAULT_QUEST))
    assert isinstance(game, QMGame)
    assert game.start_id > 0
    assert len(game.locations) > 0

def test_qm_game_basic_navigation():
    """Test basic game state navigation"""
    game = parse_qm(str(DEFAULT_QUEST))

    # Get starting location
    start_loc = game.get_location(game.start_id)
    assert start_loc.text
    assert len(start_loc.choices) > 0

    # Test choice navigation
    first_choice = start_loc.choices[0]
    next_loc = game.get_location(first_choice.jumpId)
    assert next_loc.text