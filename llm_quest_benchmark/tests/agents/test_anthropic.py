import pytest
from llm_quest_benchmark.agents.agent_factory import create_agent
from llm_quest_benchmark.constants import MODEL_CHOICES

def test_anthropic_integration(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    # Use a supported model from MODEL_CHOICES
    agent = create_agent("claude-3-5-sonnet-latest")  # Using the correct model name

    # Test basic response handling with properly formatted choices
    response = agent.get_action("Test prompt", [{"text": "Choice 1"}, {"text": "Choice 2"}])
    assert response is not None
    assert isinstance(response, int)
    assert 1 <= response <= 2  # Should be within valid range

    # Test error handling with empty choices - should raise ValueError
    with pytest.raises(ValueError, match="No choices provided"):
        agent.get_action("Test prompt", [])