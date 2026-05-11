"""Deterministic tests for Anthropic-backed harness behavior."""

from unittest.mock import Mock, patch

import pytest

from llm_quest_benchmark.harnesses.factory import create_harness


@patch("llm_quest_benchmark.llm.client.anthropic.Anthropic")
def test_anthropic_harness_mocked_completion(mock_anthropic_cls):
    """Harness should parse a mocked Anthropic completion without network calls."""
    mock_client = Mock()
    mock_response = Mock()
    mock_block = Mock()
    mock_block.text = '{"result": 2, "reasoning": "mocked"}'
    mock_response.content = [mock_block]
    mock_client.messages.create.return_value = mock_response
    mock_anthropic_cls.return_value = mock_client

    harness = create_harness("minimal", model="claude-sonnet-4-5")
    action = harness.get_action("Test prompt", [{"text": "A"}, {"text": "B"}])

    assert action == 2
    assert mock_client.messages.create.call_count == 1


def test_anthropic_harness_empty_choices_raises():
    """Base player contract should reject empty choices."""
    harness = create_harness("minimal", model="claude-sonnet-4-5")
    with pytest.raises(ValueError, match="No choices provided"):
        harness.get_action("Test prompt", [])
