"""Tests for provider-aware LLM client selection."""
from unittest.mock import Mock, patch

from llm_quest_benchmark.llm.client import (
    AnthropicClient,
    OpenAICompatibleClient,
    get_llm_client,
    parse_model_name,
)


def test_parse_model_name_with_alias():
    spec = parse_model_name("gpt-5-mini")
    assert spec.provider == "openai"
    assert spec.model_id == "gpt-5-mini"


def test_parse_model_name_with_deepseek_alias():
    spec = parse_model_name("deepseek-3.2-chat")
    assert spec.provider == "deepseek"
    assert spec.model_id == "deepseek-chat"


def test_parse_model_name_google_alias():
    spec = parse_model_name("gemini-2.5-flash")
    assert spec.provider == "google"
    assert spec.model_id == "gemini-2.5-flash"


def test_get_llm_client_deepseek():
    client = get_llm_client("deepseek-3.2-chat")
    assert isinstance(client, OpenAICompatibleClient)
    assert client.provider == "deepseek"


def test_get_llm_client_google():
    client = get_llm_client("google:gemini-2.5-flash")
    assert isinstance(client, OpenAICompatibleClient)
    assert client.provider == "google"


def test_get_llm_client_anthropic():
    client = get_llm_client("claude-sonnet-4-5")
    assert isinstance(client, AnthropicClient)


@patch("llm_quest_benchmark.llm.client.OpenAI")
def test_openai_gpt5_uses_max_completion_tokens(mock_openai_cls):
    mock_client = Mock()
    mock_chat = Mock()
    mock_completion = Mock()
    mock_msg = Mock()
    mock_msg.content = "1"
    mock_completion.choices = [Mock(message=mock_msg)]
    mock_chat.completions.create.return_value = mock_completion
    mock_client.chat = mock_chat
    mock_openai_cls.return_value = mock_client

    client = get_llm_client("gpt-5-mini")
    assert client.get_completion("pick") == "1"

    kwargs = mock_chat.completions.create.call_args.kwargs
    assert "max_completion_tokens" in kwargs
    assert "max_tokens" not in kwargs
    assert "temperature" not in kwargs


@patch("llm_quest_benchmark.llm.client.OpenAI")
def test_openai_compatible_completion_extraction(mock_openai_cls):
    mock_client = Mock()
    mock_chat = Mock()
    mock_completion = Mock()
    mock_msg = Mock()
    mock_msg.content = "1"
    mock_completion.choices = [Mock(message=mock_msg)]
    mock_chat.completions.create.return_value = mock_completion
    mock_client.chat = mock_chat
    mock_openai_cls.return_value = mock_client

    client = get_llm_client("gemini-2.5-flash")
    assert client.get_completion("pick") == "1"
    kwargs = mock_chat.completions.create.call_args.kwargs
    assert "max_tokens" in kwargs
    assert "temperature" in kwargs
