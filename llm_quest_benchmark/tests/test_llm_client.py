"""Tests for provider-aware LLM client selection."""

import subprocess
from unittest.mock import Mock, patch

from llm_quest_benchmark.llm.client import (
    AnthropicClient,
    ExecCLIClient,
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


def test_parse_model_name_codex_exec_alias():
    spec = parse_model_name("codex-exec")
    assert spec.provider == "codex_cli"
    assert spec.model_id == "codex-exec"


def test_parse_model_name_claude_exec_alias():
    spec = parse_model_name("claude-exec")
    assert spec.provider == "claude_cli"
    assert spec.model_id == "claude-exec"


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


def test_get_llm_client_codex_exec():
    client = get_llm_client("codex-exec")
    assert isinstance(client, ExecCLIClient)
    assert client.provider == "codex_cli"


def test_get_llm_client_claude_exec():
    client = get_llm_client("claude-exec")
    assert isinstance(client, ExecCLIClient)
    assert client.provider == "claude_cli"


def test_parse_model_name_haiku_alias():
    spec = parse_model_name("claude-3-5-haiku-latest")
    assert spec.provider == "anthropic"
    assert spec.model_id == "claude-3-5-haiku-latest"


@patch("llm_quest_benchmark.llm.client.OpenAI")
def test_openai_gpt5_uses_max_completion_tokens(mock_openai_cls, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
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
def test_openai_compatible_completion_extraction(mock_openai_cls, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
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
def test_openai_compatible_handles_missing_message_content(mock_openai_cls, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
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
def test_openai_usage_is_tracked(mock_openai_cls, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
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
def test_openai_usage_sums_fallback_calls(mock_openai_cls, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
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
def test_openai_gpt5_retries_empty_with_larger_budget(mock_openai_cls, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
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


@patch("llm_quest_benchmark.llm.client.subprocess.run")
def test_codex_exec_reads_output_last_message(mock_run, monkeypatch):
    monkeypatch.setattr("llm_quest_benchmark.llm.client.shutil.which", lambda command: f"/opt/{command}")
    monkeypatch.setenv("LLM_QUEST_CODEX_EXEC_MODEL", "gpt-5.4")

    def fake_run(command, **kwargs):
        output_path = command[command.index("--output-last-message") + 1]
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("2")
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout="codex\n2\ntokens used\n1,234\n",
            stderr="",
        )

    mock_run.side_effect = fake_run

    client = get_llm_client("codex-exec", system_prompt="system")
    assert client.get_completion("pick one") == "2"

    command = mock_run.call_args.args[0]
    assert command[:2] == ["/opt/codex", "exec"]
    assert "--model" in command
    assert command[command.index("--model") + 1] == "gpt-5.4"
    usage = client.get_last_usage()
    assert usage["total_tokens"] == 1234
    assert usage["prompt_tokens"] == 0
    assert usage["completion_tokens"] == 0


def test_claude_exec_uses_print_mode_and_system_prompt(monkeypatch):
    monkeypatch.setattr("llm_quest_benchmark.llm.client.shutil.which", lambda command: f"/opt/{command}")
    captured_commands = []

    def fake_run_claude(self, prompt):
        command = [
            self._command_path(),
            "-p",
            "--output-format",
            "text",
            "--max-turns",
            "1",
            "--permission-mode",
            "default",
            "--tools",
            "",
            "--no-session-persistence",
        ]
        model = self._configured_model()
        if model:
            command.extend(["--model", model])
        if self.system_prompt:
            command.extend(["--system-prompt", self.system_prompt])
        command.extend(self._extra_args())
        command.append(prompt)
        captured_commands.append(command)
        self._record_usage(0, 0)
        return "1"

    monkeypatch.setattr(ExecCLIClient, "_run_claude_exec", fake_run_claude)

    client = get_llm_client("claude-exec", system_prompt="system")
    assert client.get_completion("pick one") == "1"

    command = captured_commands[0]
    assert command[:2] == ["/opt/claude", "-p"]
    assert "--max-turns" in command
    assert "--system-prompt" in command
    assert command[command.index("--system-prompt") + 1] == "system"
    assert "--no-session-persistence" in command
