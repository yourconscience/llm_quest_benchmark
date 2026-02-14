"""Tests for LLM agent"""
import pytest
from unittest.mock import Mock, patch

from llm_quest_benchmark.agents.llm_agent import LLMAgent
from llm_quest_benchmark.schemas.response import LLMResponse


@pytest.fixture
def example_observation():
    return "You are at a trading station."


@pytest.fixture
def example_choices():
    return [
        {"id": "1", "text": "Talk to merchant"},
        {"id": "2", "text": "Leave station"}
    ]


@pytest.mark.timeout(5)  # Quick unit test
@patch('llm_quest_benchmark.llm.client.OpenAI')
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
    mock_completion.usage = Mock(prompt_tokens=9, completion_tokens=2, total_tokens=11)
    mock_chat.completions.create.return_value = mock_completion
    mock_openai.return_value.chat = mock_chat

    # Test data
    observation = "You are at a trading station."
    choices = [
        {"id": "1", "text": "Talk to merchant"},
        {"id": "2", "text": "Leave station"}
    ]

    # Create agent and test
    agent = LLMAgent(model_name="gpt-5-mini")
    result = agent.get_action(observation, choices)

    # Verify results
    assert result == 1  # Expect an integer
    assert mock_chat.completions.create.call_count == 1
    last_response = agent.get_last_response()
    assert last_response.prompt_tokens == 9
    assert last_response.completion_tokens == 2
    assert last_response.total_tokens == 11


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


def test_agent_initialization_without_api_key(monkeypatch):
    """Agent construction should not require provider API keys before inference."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    agent = LLMAgent(model_name="gpt-5-mini")
    assert agent.llm is None


def test_gemini_prompt_uses_number_mode():
    agent = LLMAgent(model_name="gemini-2.5-flash")
    prompt = agent._format_prompt("state", [{"text": "A"}, {"text": "B"}])
    assert "Return only one integer from 1 to 2." in prompt
    assert "Return ONLY valid JSON" not in prompt


def test_non_gemini_prompt_uses_selected_template():
    agent = LLMAgent(model_name="gpt-5-mini", action_template="stub.jinja")
    prompt = agent._format_prompt("state", [{"text": "A"}, {"text": "B"}])
    assert "IMPORTANT: Please respond with ONLY a single number" in prompt


def test_contextual_state_includes_previous_observations():
    agent = LLMAgent(model_name="gpt-5-mini")
    agent._remember_observation("Previous hint")
    agent._remember_observation("Current state")
    contextual = agent._build_contextual_state("Current state")
    assert "Recent context from previous steps" in contextual
    assert "Previous hint" in contextual


def test_safety_filter_prefers_lower_risk_choice():
    agent = LLMAgent(model_name="gpt-5-mini")
    choices = [
        {"text": "Пойти в космопорт и улететь, чтобы завтра не позориться"},
        {"text": "Постараться пройти мимо"},
    ]
    assert agent._apply_safety_filter(1, choices) == 2


def test_get_last_response_uses_skip_single_result():
    agent = LLMAgent(model_name="gpt-5-mini", skip_single=True)
    agent.history.append(LLMResponse(action=2, is_default=False))
    agent._last_response = LLMResponse(action=2, is_default=False)

    action = agent.get_action("state", [{"id": "1", "text": "Only option"}])

    assert action == 1
    assert agent.get_last_response().action == 1
    assert agent.get_last_response().reasoning == "auto_single_choice"
