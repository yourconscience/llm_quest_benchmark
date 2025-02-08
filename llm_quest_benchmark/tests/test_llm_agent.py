"""Basic tests for LLM agent functionality"""
import pytest
from unittest.mock import patch
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
    return "1"  # Всегда выбираем первый вариант для тестов

def test_agent_initialization():
    """Test that agent can be created"""
    agent = QuestAgent()
    assert agent.system_template
    assert agent.action_template

@patch('textarena.agents.OpenRouterAgent.__call__')
def test_agent_response_format(mock_call, example_observation, mock_openrouter_response):
    """Test that agent returns valid action number"""
    mock_call.return_value = mock_openrouter_response

    agent = QuestAgent()
    response = agent(example_observation)

    assert response.strip().isdigit()
    choice_num = int(response.strip())
    assert 1 <= choice_num <= 2

def test_template_rendering():
    """Test that templates are rendered correctly"""
    agent = QuestAgent()

    # Test action template only (system prompt тестируем отдельно)
    action_prompt = agent.action_template.render(
        observation="Test location",
        choices=[{"text": "Option 1"}, {"text": "Option 2"}]
    )
    assert "Test location" in action_prompt
    assert "Option 1" in action_prompt
    assert "Option 2" in action_prompt