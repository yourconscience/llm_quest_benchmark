"""Deterministic tests for Anthropic-backed agent behavior."""
import pytest
from unittest.mock import Mock, patch

from llm_quest_benchmark.agents.agent_factory import create_agent


@patch("llm_quest_benchmark.llm.client.anthropic.Anthropic")
def test_anthropic_agent_mocked_completion(mock_anthropic_cls):
    """Agent should parse a mocked Anthropic completion without network calls."""
    mock_client = Mock()
    mock_response = Mock()
    mock_block = Mock()
    mock_block.text = '{"result": 2, "reasoning": "mocked"}'
    mock_response.content = [mock_block]
    mock_client.messages.create.return_value = mock_response
    mock_anthropic_cls.return_value = mock_client

    agent = create_agent("claude-sonnet-4-5")
    action = agent.get_action("Test prompt", [{"text": "A"}, {"text": "B"}])

    assert action == 2
    assert mock_client.messages.create.call_count == 1


def test_anthropic_agent_empty_choices_raises():
    """Base player contract should reject empty choices."""
    agent = create_agent("claude-sonnet-4-5")
    with pytest.raises(ValueError, match="No choices provided"):
        agent.get_action("Test prompt", [])
