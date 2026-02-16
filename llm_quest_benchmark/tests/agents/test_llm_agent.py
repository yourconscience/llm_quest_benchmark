"""Tests for LLM agent"""
import pytest
from unittest.mock import Mock, patch

from llm_quest_benchmark.agents.llm_agent import LLMAgent, parse_llm_response
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


def test_gemini_prompt_uses_selected_template():
    agent = LLMAgent(model_name="gemini-2.5-flash")
    prompt = agent._format_prompt("state", [{"text": "A"}, {"text": "B"}])
    assert "Return ONLY valid JSON" in prompt
    assert "A" in prompt
    assert "B" in prompt


def test_non_gemini_prompt_uses_selected_template():
    agent = LLMAgent(model_name="gpt-5-mini", action_template="stub.jinja")
    prompt = agent._format_prompt("state", [{"text": "A"}, {"text": "B"}])
    assert "IMPORTANT: Please respond with ONLY a single number" in prompt


def test_gpt5_force_numeric_retry_path():
    agent = LLMAgent(model_name="gpt-5-mini")
    mocked_llm = Mock()
    mocked_llm.get_completion.side_effect = ["```json\n{", "```json\n{", "2"]
    mocked_llm.get_last_usage.side_effect = [
        {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12, "estimated_cost_usd": 0.001},
        {"prompt_tokens": 6, "completion_tokens": 1, "total_tokens": 7, "estimated_cost_usd": 0.0005},
        {"prompt_tokens": 4, "completion_tokens": 1, "total_tokens": 5, "estimated_cost_usd": 0.0003},
    ]
    agent.llm = mocked_llm

    action = agent.get_action("state", [{"text": "A"}, {"text": "B"}])

    assert action == 2
    assert mocked_llm.get_completion.call_count == 3
    last = agent.get_last_response()
    assert last.total_tokens == 24
    assert last.estimated_cost_usd == pytest.approx(0.0018)


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


def test_parse_llm_response_extracts_fields_without_strict_json():
    raw = "Reasoning: safer path\nAnalysis: low fuel, need pit stop\n2"
    parsed = parse_llm_response(raw, num_choices=3)
    assert parsed.action == 2
    assert parsed.reasoning is not None
    assert "safer path" in parsed.reasoning
    assert parsed.analysis is not None
    assert "low fuel" in parsed.analysis


def test_parse_llm_response_uses_analysis_as_reasoning_when_truncated():
    raw = '2\n{"analysis":"Low stats: avoid fight and prepare via library'
    parsed = parse_llm_response(raw, num_choices=4)
    assert parsed.action == 2
    assert parsed.analysis is not None
    assert "avoid fight" in parsed.analysis
    assert parsed.reasoning is not None
    assert "avoid fight" in parsed.reasoning
    assert not parsed.reasoning.startswith("raw_response:")


def test_llm_error_default_response_keeps_reasoning_marker():
    agent = LLMAgent(model_name="gemini-2.5-flash")
    mocked_llm = Mock()
    mocked_llm.get_completion.side_effect = RuntimeError("provider returned empty message")
    mocked_llm.get_last_usage.return_value = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "estimated_cost_usd": None,
    }
    agent.llm = mocked_llm

    action = agent.get_action("state", [{"text": "A"}, {"text": "B"}])

    assert action == 1
    last = agent.get_last_response()
    assert last.is_default is True
    assert last.reasoning is not None
    assert "llm_call_error" in last.reasoning


def test_retry_prompt_requests_json_payload():
    agent = LLMAgent(model_name="gemini-2.5-flash")
    prompt = agent._format_retry_prompt("state", [{"text": "A"}, {"text": "B"}])
    assert "Return valid JSON only" in prompt
    assert '"analysis"' in prompt
    assert '"reasoning"' in prompt
    assert '"result"' in prompt


def test_retry_preserves_reasoning_from_first_attempt():
    agent = LLMAgent(model_name="gemini-2.5-flash")
    mocked_llm = Mock()
    mocked_llm.get_completion.side_effect = [
        "Analysis: low oxygen\nReasoning: safer move first\n```json\n{",
        "2",
    ]
    mocked_llm.get_last_usage.side_effect = [
        {
            "prompt_tokens": 100,
            "completion_tokens": 10,
            "total_tokens": 110,
            "estimated_cost_usd": 0.001,
        },
        {
            "prompt_tokens": 20,
            "completion_tokens": 2,
            "total_tokens": 22,
            "estimated_cost_usd": 0.0002,
        },
    ]
    agent.llm = mocked_llm

    action = agent.get_action("state", [{"text": "A"}, {"text": "B"}])

    assert action == 2
    last = agent.get_last_response()
    assert last.analysis is not None
    assert "low oxygen" in last.analysis
    assert last.reasoning is not None
    assert "safer move first" in last.reasoning


def test_loop_escape_diversifies_repeated_state_action():
    agent = LLMAgent(model_name="gemini-2.5-flash")
    mocked_llm = Mock()
    mocked_llm.get_completion.side_effect = ["1", "1", "1", "1"]
    mocked_llm.get_last_usage.return_value = {
        "prompt_tokens": 10,
        "completion_tokens": 2,
        "total_tokens": 12,
        "estimated_cost_usd": 0.0001,
    }
    agent.llm = mocked_llm

    choices = [{"text": "Option A"}, {"text": "Option B"}]
    state = "Looping state"

    first = agent.get_action(state, choices)
    second = agent.get_action(state, choices)
    third = agent.get_action(state, choices)
    fourth = agent.get_action(state, choices)

    assert first == 1
    # Conservative loop escape should diversify after deeper repetition.
    assert second == 1
    assert third == 1
    assert fourth == 2
    assert "loop_escape_diversify" in (agent.get_last_response().reasoning or "")
