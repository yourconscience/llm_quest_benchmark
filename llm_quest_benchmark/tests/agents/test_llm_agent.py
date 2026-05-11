"""Tests for the base LLM harness behavior."""

from unittest.mock import Mock, patch

import pytest

from llm_quest_benchmark.harnesses.base import parse_llm_response
from llm_quest_benchmark.harnesses.minimal import MinimalHarness
from llm_quest_benchmark.schemas.response import LLMResponse


@pytest.fixture
def example_observation():
    return "You are at a trading station."


@pytest.fixture
def example_choices():
    return [{"id": "1", "text": "Talk to merchant"}, {"id": "2", "text": "Leave station"}]


@pytest.mark.timeout(5)  # Quick unit test
@patch("llm_quest_benchmark.llm.client.OpenAI")
def test_harness_basic_flow(mock_openai, monkeypatch):
    """Test basic harness functionality with mocked LLM"""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
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
    choices = [{"id": "1", "text": "Talk to merchant"}, {"id": "2", "text": "Leave station"}]

    # Create harness and test
    harness = MinimalHarness(model_name="gpt-5-mini")
    result = harness.get_action(observation, choices)

    # Verify results
    assert result == 1  # Expect an integer
    assert mock_chat.completions.create.call_count == 1
    last_response = harness.get_last_response()
    assert last_response.prompt_tokens == 9
    assert last_response.completion_tokens == 2
    assert last_response.total_tokens == 11


def test_template_rendering():
    """Test that templates are rendered correctly"""
    harness = MinimalHarness()
    observation = "Test observation"
    choices = [{"text": "Option 1"}, {"text": "Option 2"}]

    # Test that prompt is rendered correctly
    prompt = harness.prompt_renderer.render_action_prompt(observation, choices)
    assert "Test observation" in prompt
    assert "Option 1" in prompt
    assert "Option 2" in prompt


def test_harness_initialization_without_api_key(monkeypatch):
    """Harness construction should not require provider API keys before inference."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    harness = MinimalHarness(model_name="gpt-5-mini")
    assert harness.llm is None


def test_gemini_prompt_uses_selected_template():
    harness = MinimalHarness(model_name="gemini-2.5-flash", action_template="reasoning.jinja")
    prompt = harness._format_prompt("state", [{"text": "A"}, {"text": "B"}])
    assert "Return ONLY valid JSON" in prompt
    assert "A" in prompt
    assert "B" in prompt


def test_non_gemini_prompt_uses_selected_template():
    harness = MinimalHarness(model_name="gpt-5-mini", action_template="stub.jinja")
    prompt = harness._format_prompt("state", [{"text": "A"}, {"text": "B"}])
    assert "IMPORTANT: Please respond with ONLY a single number" in prompt


def test_template_alias_without_suffix_is_supported():
    harness = MinimalHarness(model_name="gpt-5-mini", action_template="reasoning")
    prompt = harness._format_prompt("state", [{"text": "A"}, {"text": "B"}])
    assert '"result"' in prompt


def test_gpt5_force_numeric_retry_path():
    harness = MinimalHarness(model_name="gpt-5-mini")
    mocked_llm = Mock()
    mocked_llm.get_completion.side_effect = ["```json\n{", "```json\n{", "2"]
    mocked_llm.get_last_usage.side_effect = [
        {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12, "estimated_cost_usd": 0.001},
        {"prompt_tokens": 6, "completion_tokens": 1, "total_tokens": 7, "estimated_cost_usd": 0.0005},
        {"prompt_tokens": 4, "completion_tokens": 1, "total_tokens": 5, "estimated_cost_usd": 0.0003},
    ]
    harness.llm = mocked_llm

    action = harness.get_action("state", [{"text": "A"}, {"text": "B"}])

    assert action == 2
    assert mocked_llm.get_completion.call_count == 3
    last = harness.get_last_response()
    assert last.total_tokens == 24
    assert last.estimated_cost_usd == pytest.approx(0.0018)
    assert last.parse_mode == "force_retry_number_only"


def test_contextual_state_includes_previous_observations():
    harness = MinimalHarness(model_name="gpt-5-mini")
    harness.memory_module.update({"observation": "Previous hint"})
    harness.memory_module.update({"observation": "Current state"})
    contextual = harness._build_contextual_state("Current state")
    assert "Recent context from previous steps" in contextual
    assert "Previous hint" in contextual


def test_contextual_state_includes_recent_decisions():
    harness = MinimalHarness(model_name="gpt-5-mini")
    harness.memory_module.update({"observation": "Previous state"})
    harness.memory_module.update({"action": 2, "choice": "Inspect the terminal", "parse_mode": "json_direct"})
    harness.memory_module.update({"action": 1, "choice": "Ask for access", "parse_mode": "retry_json_repaired"})
    contextual = harness._build_contextual_state("Current state")
    assert "Recent selected actions" in contextual
    assert "Inspect the terminal" in contextual
    assert "parse=json_direct" in contextual


def test_safety_filter_prefers_lower_risk_choice():
    harness = MinimalHarness(model_name="gpt-5-mini")
    choices = [
        {"text": "Пойти в космопорт и улететь, чтобы завтра не позориться"},
        {"text": "Постараться пройти мимо"},
    ]
    assert harness._apply_safety_filter(choices, 1) == 2


def test_get_last_response_uses_skip_single_result():
    harness = MinimalHarness(model_name="gpt-5-mini", skip_single=True)
    harness.history.append(LLMResponse(action=2, is_default=False))
    harness._last_response = LLMResponse(action=2, is_default=False)

    action = harness.get_action("state", [{"id": "1", "text": "Only option"}])

    assert action == 1
    assert harness.get_last_response().action == 1
    assert harness.get_last_response().reasoning == "auto_single_choice"


def test_parse_llm_response_number_only_tracks_parse_mode():
    parsed = parse_llm_response("2", num_choices=3)
    assert parsed.action == 2
    assert parsed.parse_mode == "number_only"
    assert parsed.is_default is False


def test_parse_llm_response_default_sets_parse_mode():
    parsed = parse_llm_response("no valid action", num_choices=3)
    assert parsed.action == 1
    assert parsed.parse_mode == "default_first"
    assert parsed.is_default is True


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
    harness = MinimalHarness(model_name="gemini-2.5-flash")
    mocked_llm = Mock()
    mocked_llm.get_completion.side_effect = RuntimeError("provider returned empty message")
    mocked_llm.get_last_usage.return_value = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "estimated_cost_usd": None,
    }
    harness.llm = mocked_llm

    action = harness.get_action("state", [{"text": "A"}, {"text": "B"}])

    assert action == 1
    last = harness.get_last_response()
    assert last.is_default is True
    assert last.reasoning is not None
    assert "llm_call_error" in last.reasoning


def test_retry_prompt_requests_json_payload():
    harness = MinimalHarness(model_name="gemini-2.5-flash")
    prompt = harness._format_retry_prompt("state", [{"text": "A"}, {"text": "B"}])
    assert "Return valid JSON only" in prompt
    assert '"analysis"' in prompt
    assert '"reasoning"' in prompt
    assert '"result"' in prompt


def test_retry_preserves_reasoning_from_first_attempt():
    harness = MinimalHarness(model_name="gemini-2.5-flash")
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
    harness.llm = mocked_llm

    action = harness.get_action("state", [{"text": "A"}, {"text": "B"}])

    assert action == 2
    last = harness.get_last_response()
    assert last.analysis is not None
    assert "low oxygen" in last.analysis
    assert last.reasoning is not None
    assert "safer move first" in last.reasoning
