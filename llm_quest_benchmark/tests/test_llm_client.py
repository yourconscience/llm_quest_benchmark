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


def test_parse_model_name_haiku_alias():
    spec = parse_model_name("claude-3-5-haiku-latest")
    assert spec.provider == "anthropic"
    assert spec.model_id == "claude-3-5-haiku-latest"


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


@patch("llm_quest_benchmark.llm.client.OpenAI")
def test_openai_compatible_handles_missing_message_content(mock_openai_cls):
    mock_client = Mock()
    mock_chat = Mock()
    mock_completion = Mock()
    mock_completion.choices = [Mock(message=None)]
    mock_chat.completions.create.return_value = mock_completion
    mock_client.chat = mock_chat
    mock_openai_cls.return_value = mock_client

    client = get_llm_client("gemini-2.5-flash")
    assert client.get_completion("pick") == ""


@patch("llm_quest_benchmark.llm.client.OpenAI")
def test_openai_usage_is_tracked(mock_openai_cls):
    mock_client = Mock()
    mock_chat = Mock()
    mock_completion = Mock()
    mock_msg = Mock()
    mock_msg.content = "1"
    mock_completion.choices = [Mock(message=mock_msg)]
    mock_completion.usage = Mock(prompt_tokens=11, completion_tokens=4, total_tokens=15)
    mock_chat.completions.create.return_value = mock_completion
    mock_client.chat = mock_chat
    mock_openai_cls.return_value = mock_client

    client = get_llm_client("gpt-5-mini")
    assert client.get_completion("pick") == "1"
    usage = client.get_last_usage()
    assert usage["prompt_tokens"] == 11
    assert usage["completion_tokens"] == 4
    assert usage["total_tokens"] == 15
    assert "estimated_cost_usd" in usage


@patch("llm_quest_benchmark.llm.client.OpenAI")
def test_openai_usage_sums_fallback_calls(mock_openai_cls):
    mock_client = Mock()
    mock_chat = Mock()
    first = Mock()
    second = Mock()
    first.choices = [Mock(message=Mock(content=""))]
    first.usage = Mock(prompt_tokens=20, completion_tokens=1, total_tokens=21)
    second.choices = [Mock(message=Mock(content="1"))]
    second.usage = Mock(prompt_tokens=30, completion_tokens=2, total_tokens=32)
    mock_chat.completions.create.side_effect = [first, second]
    mock_client.chat = mock_chat
    mock_openai_cls.return_value = mock_client

    client = get_llm_client("gpt-5-mini")
    assert client.get_completion("pick") == "1"
    usage = client.get_last_usage()
    assert usage["prompt_tokens"] == 50
    assert usage["completion_tokens"] == 3
    assert usage["total_tokens"] == 53


@patch("llm_quest_benchmark.llm.client.OpenAI")
def test_openai_gpt5_retries_empty_with_larger_budget(mock_openai_cls):
    mock_client = Mock()
    mock_chat = Mock()
    first = Mock()
    second = Mock()
    first.choices = [Mock(message=Mock(content=""))]
    second.choices = [Mock(message=Mock(content="1"))]
    mock_chat.completions.create.side_effect = [first, second]
    mock_client.chat = mock_chat
    mock_openai_cls.return_value = mock_client

    client = get_llm_client("gpt-5-mini")
    assert client.get_completion("pick") == "1"
    assert mock_chat.completions.create.call_count == 2
    second_kwargs = mock_chat.completions.create.call_args_list[1].kwargs
    assert second_kwargs["max_completion_tokens"] >= 800
