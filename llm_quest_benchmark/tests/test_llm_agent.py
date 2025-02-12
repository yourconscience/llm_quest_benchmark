"""Tests for LLM agent"""
import pytest
from unittest.mock import Mock, patch

from llm_quest_benchmark.agents.simple_agent import SimpleQuestAgent


@pytest.fixture
def example_observation():
    return "You are at a trading station.\n\nAvailable actions:\n1. Talk to merchant\n2. Leave station\n"


@pytest.fixture
def mock_openrouter_response():
    return "1"


@patch('llm_quest_benchmark.agents.llm_client.OpenAIClient')
def test_agent_response_format(mock_client_class, example_observation, mock_openrouter_response):
    """Test that agent returns valid action number"""
    # Setup mock
    mock_client = Mock()
    mock_client.side_effect = lambda x: mock_openrouter_response
    mock_client_class.return_value = mock_client

    # Create agent and test
    agent = SimpleQuestAgent(model_name="gpt-4o")
    response = agent(example_observation)

    assert response == "1"
    assert mock_client.call_count == 1


def test_template_rendering():
    """Test that templates are rendered correctly"""
    agent = SimpleQuestAgent()
    observation = "Test observation"
    choices = [{"text": "Option 1"}, {"text": "Option 2"}]

    # Test that prompt is rendered correctly
    prompt = agent.action_template.render(observation=observation, choices=choices)
    assert "Test observation" in prompt
    assert "Option 1" in prompt
    assert "Option 2" in prompt
