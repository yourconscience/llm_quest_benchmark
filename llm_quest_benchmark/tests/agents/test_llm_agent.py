"""Tests for LLM agent"""
import pytest
from unittest.mock import Mock, patch

from llm_quest_benchmark.agents.llm_agent import LLMAgent


@pytest.fixture
def example_observation():
    return "You are at a trading station."


@pytest.fixture
def example_choices():
    return [
        {"id": "1", "text": "Talk to merchant"},
        {"id": "2", "text": "Leave station"}
    ]


@pytest.fixture
def mock_openrouter_response():
    return "1"


@pytest.mark.timeout(5)  # Quick unit test
@patch('llm_quest_benchmark.agents.llm_client.OpenAI')
def test_agent_basic_flow(mock_openai):
    """Test basic agent functionality with mocked LLM"""
    # Setup mock
    mock_chat = Mock()
    mock_completion = Mock()
    mock_choice = Mock()
    mock_message = Mock()

    # Setup response chain
    mock_message.content = "1"
    mock_choice.message = mock_message
    mock_completion.choices = [mock_choice]
    mock_chat.completions.create.return_value = mock_completion
    mock_openai.return_value.chat = mock_chat

    # Test data
    observation = "You are at a trading station."
    choices = [
        {"id": "1", "text": "Talk to merchant"},
        {"id": "2", "text": "Leave station"}
    ]

    # Create agent and test
    agent = LLMAgent(model_name="gpt-4o")
    result = agent.get_action(observation, choices)

    # Verify results
    assert result == "1"
    assert mock_chat.completions.create.call_count == 1


def test_template_rendering():
    """Test that templates are rendered correctly"""
    agent = LLMAgent()
    observation = "Test observation"
    choices = [{"text": "Option 1"}, {"text": "Option 2"}]

    # Test that prompt is rendered correctly
    prompt = agent.prompt_renderer.render_action_prompt(observation, choices)
    assert "Test observation" in prompt
    assert "Option 1" in prompt
    assert "Option 2" in prompt
