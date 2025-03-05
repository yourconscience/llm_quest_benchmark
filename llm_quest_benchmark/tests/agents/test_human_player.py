"""Unit tests for HumanPlayer"""
import pytest
from unittest.mock import patch

from llm_quest_benchmark.agents.human_player import HumanPlayer


def test_human_player_initialization():
    """Test HumanPlayer initialization"""
    player = HumanPlayer(skip_single=True)
    assert player.skip_single is True


def test_human_player_single_choice_skipping():
    """Test that single choices are auto-selected when skip_single is True"""
    player = HumanPlayer(skip_single=True)
    choices = [{"text": "Only choice"}]
    action = player.get_action("Test observation", choices)
    assert action == 1


@patch('builtins.input', return_value='1')
def test_human_player_valid_input(mock_input):
    """Test HumanPlayer with valid input"""
    player = HumanPlayer()
    choices = [{"text": "Choice 1"}, {"text": "Choice 2"}]
    action = player.get_action("Test observation", choices)
    assert action == 1


@patch('builtins.input', side_effect=['invalid', 'abc', '2'])
def test_human_player_invalid_input(mock_input):
    """Test HumanPlayer handles invalid input correctly"""
    player = HumanPlayer()
    choices = [{"text": "Choice 1"}, {"text": "Choice 2"}]
    action = player.get_action("Test observation", choices)
    assert action == 2


def test_human_player_no_choices():
    """Test HumanPlayer raises error when no choices provided"""
    player = HumanPlayer()
    with pytest.raises(ValueError):
        player.get_action("Test observation", [])
