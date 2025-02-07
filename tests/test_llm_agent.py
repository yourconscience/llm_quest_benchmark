"""Basic tests for LLM agent functionality"""
import pytest
from src.llm_agent import QuestAgent
from pathlib import Path

@pytest.fixture
def example_observation():
    return """You are at a trading station.
    
Available actions:
1. Talk to merchant
2. Leave station
"""

def test_agent_initialization():
    """Test that agent can be created"""
    agent = QuestAgent()
    assert agent.system_template
    assert agent.action_template

def test_agent_response_format(example_observation):
    """Test that agent returns valid action number"""
    agent = QuestAgent()
    response = agent(example_observation)
    
    # Response should be a string containing a number
    assert response.strip().isdigit()
    choice_num = int(response.strip())
    assert 1 <= choice_num <= 2

def test_template_rendering():
    """Test that templates are rendered correctly"""
    agent = QuestAgent()
    
    # Test system prompt
    system_prompt = agent.system_template.render()
    assert "text quest" in system_prompt.lower()
    
    # Test action template
    action_prompt = agent.action_template.render(
        observation="Test location",
        choices=[{"text": "Option 1"}, {"text": "Option 2"}]
    )
    assert "Test location" in action_prompt
    assert "Option 1" in action_prompt
    assert "Option 2" in action_prompt 