"""Basic tests for LLM agent functionality"""
import pytest
from unittest.mock import patch, Mock

from llm_quest_benchmark.agents.llm_agent import QuestAgent


@pytest.fixture
def example_observation():
    return """You are at a trading station.

Available actions:
1. Talk to merchant
2. Leave station
"""


@pytest.fixture
def mock_openrouter_response():
    return "1"  # Always choose first option for tests


@patch('textarena.agents.OpenRouterAgent')
def test_agent_response_format(mock_agent_class, example_observation, mock_openrouter_response):
    """Test that agent returns valid action number"""
    # Setup mock
    mock_agent_instance = Mock()
    mock_agent_instance.__call__.return_value = mock_openrouter_response
    mock_agent_class.return_value = mock_agent_instance

    # Create and test agent
    agent = QuestAgent(model_name="sonnet")  # Use sonnet model for testing
    response = agent(example_observation)

    assert response.strip().isdigit()
    choice_num = int(response.strip())
    assert 1 <= choice_num <= 2


def test_template_rendering():
    """Test that templates are rendered correctly"""
    agent = QuestAgent()

    # Test action template only (system prompt тестируем отдельно)
    action_prompt = agent.action_template.render(observation="Test location",
                                                 choices=[{
                                                     "text": "Option 1"
                                                 }, {
                                                     "text": "Option 2"
                                                 }])
    assert "Test location" in action_prompt
    assert "Option 1" in action_prompt
    assert "Option 2" in action_prompt
