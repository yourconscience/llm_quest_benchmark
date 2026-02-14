"""Tests for provider-aware LLM client selection."""
from unittest.mock import Mock, patch

from llm_quest_benchmark.llm.client import (
    AnthropicClient,
    OpenAICompatibleClient,
    get_llm_client,
    parse_model_name,
)


def test_parse_model_name_with_alias():
    spec = parse_model_name("gpt-4o-mini")
    assert spec.provider == "openai"
    assert spec.model_id == "gpt-4o-mini"


def test_parse_model_name_with_provider_prefix():
    spec = parse_model_name("openrouter:openai/gpt-4o-mini")
    assert spec.provider == "openrouter"
    assert spec.model_id == "openai/gpt-4o-mini"


def test_parse_model_name_google_alias():
    spec = parse_model_name("gemini-2.5-flash")
    assert spec.provider == "google"
    assert spec.model_id == "gemini-2.5-flash"


def test_get_llm_client_openrouter():
    client = get_llm_client("openrouter:openai/gpt-4o-mini")
    assert isinstance(client, OpenAICompatibleClient)
    assert client.provider == "openrouter"


def test_get_llm_client_deepseek():
    client = get_llm_client("deepseek:deepseek-chat")
    assert isinstance(client, OpenAICompatibleClient)
    assert client.provider == "deepseek"


def test_get_llm_client_google():
    client = get_llm_client("google:gemini-2.5-flash")
    assert isinstance(client, OpenAICompatibleClient)
    assert client.provider == "google"


def test_get_llm_client_anthropic():
    client = get_llm_client("claude-3-5-haiku-latest")
    assert isinstance(client, AnthropicClient)


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

    client = get_llm_client("gpt-4o-mini")
    assert client.get_completion("pick") == "1"
