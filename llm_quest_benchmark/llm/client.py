"""LLM client interface for different model providers"""

import logging
import os
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anthropic
from dotenv import load_dotenv

# Load .env BEFORE checking Langfuse (needs LANGFUSE_SECRET_KEY from .env).
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env", override=False)

from llm_quest_benchmark.llm.tracing import is_enabled as _langfuse_enabled  # noqa: E402

if _langfuse_enabled():
    from langfuse import observe  # noqa: E402
    from langfuse.openai import OpenAI  # noqa: E402
else:
    from openai import OpenAI  # noqa: E402

    def observe(**_kwargs):  # type: ignore[misc]
        def _noop(fn):
            return fn

        return _noop


from llm_quest_benchmark.constants import (  # noqa: E402
    DEFAULT_TEMPERATURE,
    MODEL_ALIASES,
    MODEL_PROVIDER_CONFIG,
)
from llm_quest_benchmark.llm.cost import UsageStats, estimate_cost_usd  # noqa: E402

logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)


@dataclass(frozen=True)
class ModelSpec:
    """Normalized model specification."""

    provider: str
    model_id: str


def _get_attr_or_key(value: Any, key: str, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_model_name(model_name: str) -> ModelSpec:
    """Parse model name into provider/model pair."""
    normalized = MODEL_ALIASES.get(model_name, model_name)
    if ":" in normalized:
        provider, model_id = normalized.split(":", 1)
    elif normalized.startswith("claude"):
        provider, model_id = "anthropic", normalized
    elif normalized.startswith("gemini"):
        provider, model_id = "google", normalized
    elif normalized.startswith("deepseek"):
        provider, model_id = "deepseek", normalized
    elif normalized.startswith("o") or normalized.startswith("gpt"):
        provider, model_id = "openai", normalized
    else:
        raise NotImplementedError(f"Model {model_name} is not supported")

    provider = provider.strip().lower()
    model_id = model_id.strip()
    if provider not in MODEL_PROVIDER_CONFIG:
        raise NotImplementedError(f"Provider {provider} is not supported")
    if not model_id:
        raise NotImplementedError(f"Model name {model_name} is invalid")
    return ModelSpec(provider=provider, model_id=model_id)


def is_supported_model_name(model_name: str) -> bool:
    """Return True when model name can be parsed into a supported provider."""
    if model_name in ("random_choice", "human"):
        return True
    try:
        parse_model_name(model_name)
        return True
    except Exception:
        return False


class LLMClient(ABC):
    """Base class for LLM clients"""

    def __init__(
        self,
        model_id: str = "",
        provider: str = "",
        system_prompt: str = "",
        temperature: float = DEFAULT_TEMPERATURE,
        request_timeout: int = 30,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.8,
    ):
        self.model_id = model_id
        self.provider = provider
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.request_timeout = request_timeout
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self._last_usage = UsageStats()
        self._total_prompt_tokens = 0
        self._total_completion_tokens = 0
        self._total_estimated_cost_usd = 0.0
        self._priced_calls = 0

    @abstractmethod
    def get_completion(self, prompt: str) -> str:
        """Get a completion from the model."""
        pass

    def _with_retries(self, fn: Callable[[], str]) -> str:
        """Run an LLM request function with bounded retries and backoff."""
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                return fn()
            except Exception as exc:
                last_error = exc
                if attempt == self.max_retries:
                    break
                sleep_time = self.retry_backoff_seconds * (2**attempt)
                logger.warning(
                    "LLM request failed (attempt %s/%s): %s. Retrying in %.1fs",
                    attempt + 1,
                    self.max_retries + 1,
                    exc,
                    sleep_time,
                )
                time.sleep(sleep_time)
        raise RuntimeError(f"LLM request failed after {self.max_retries + 1} attempts: {last_error}") from last_error

    def __call__(self, prompt: str) -> str:
        """Get a completion from the model."""
        return self.get_completion(prompt)

    def _record_usage(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int | None = None,
    ) -> None:
        prompt_tokens = int(prompt_tokens)
        completion_tokens = int(completion_tokens)
        if total_tokens is not None:
            total_tokens = int(total_tokens)
        else:
            total_tokens = prompt_tokens + completion_tokens
        estimated_cost_usd = estimate_cost_usd(
            self.provider,
            self.model_id,
            prompt_tokens,
            completion_tokens,
        )
        self._last_usage = UsageStats(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=estimated_cost_usd,
        )
        self._total_prompt_tokens += prompt_tokens
        self._total_completion_tokens += completion_tokens
        if estimated_cost_usd is not None:
            self._total_estimated_cost_usd += float(estimated_cost_usd)
            self._priced_calls += 1

    def get_last_usage(self) -> dict[str, Any]:
        """Get usage from the most recent completion call."""
        return self._last_usage.to_dict()

    def get_total_usage(self) -> dict[str, Any]:
        """Get accumulated usage for all completion calls."""
        total_tokens = self._total_prompt_tokens + self._total_completion_tokens
        estimated_cost = self._total_estimated_cost_usd if self._priced_calls > 0 else None
        return {
            "prompt_tokens": self._total_prompt_tokens,
            "completion_tokens": self._total_completion_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": estimated_cost,
        }


class OpenAICompatibleClient(LLMClient):
    """Client for OpenAI-compatible chat-completions APIs."""

    def __init__(
        self,
        provider: str,
        model_id: str = "",
        system_prompt: str = "",
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = 200,
        request_timeout: int = 30,
    ):
        super().__init__(
            model_id=model_id,
            provider=provider,
            system_prompt=system_prompt,
            temperature=temperature,
            request_timeout=request_timeout,
        )
        self.provider = provider
        self.max_tokens = max_tokens
        self._client: OpenAI | None = None
        self._temperature_warning_emitted = False

    def _require_api_key(self, env_var: str) -> str:
        value = os.getenv(env_var)
        if value:
            return value
        raise RuntimeError(
            f"Missing API key for provider '{self.provider}'. Set {env_var} in your environment or .env file."
        )

    def _provider_settings(self) -> tuple[str | None, str | None]:
        if self.provider == "openai":
            return self._require_api_key("OPENAI_API_KEY"), None
        if self.provider == "google":
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "Missing API key for provider 'google'. "
                    "Set GOOGLE_API_KEY (or GEMINI_API_KEY) in your environment or .env file."
                )
            return api_key, "https://generativelanguage.googleapis.com/v1beta/openai/"
        if self.provider == "openrouter":
            return self._require_api_key("OPENROUTER_API_KEY"), "https://openrouter.ai/api/v1"
        if self.provider == "deepseek":
            return self._require_api_key("DEEPSEEK_API_KEY"), "https://api.deepseek.com/v1"
        raise NotImplementedError(f"Unsupported OpenAI-compatible provider: {self.provider}")

    def _get_client(self) -> OpenAI:
        if self._client is None:
            api_key, base_url = self._provider_settings()
            kwargs = {"api_key": api_key, "timeout": self.request_timeout, "max_retries": 0}
            if base_url:
                kwargs["base_url"] = base_url
            self._client = OpenAI(**kwargs)
        return self._client

    @staticmethod
    def _extract_content(response: Any) -> str:
        choices = _get_attr_or_key(response, "choices", []) or []
        if not choices:
            return ""

        first_choice = choices[0]
        message = _get_attr_or_key(first_choice, "message")
        if message is None:
            # Some OpenAI-compatible providers can occasionally return a choice
            # without message content; treat it as empty output.
            return ""

        content = _get_attr_or_key(message, "content")
        if content is None:
            return ""
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict):
                    parts.append(part.get("text", ""))
                else:
                    parts.append(getattr(part, "text", ""))
            return "\n".join(p for p in parts if p).strip()
        return str(content).strip()

    @staticmethod
    def _extract_usage(response: Any) -> tuple[int, int]:
        usage = _get_attr_or_key(response, "usage")
        prompt_tokens = _get_attr_or_key(usage, "prompt_tokens", 0)
        completion_tokens = _get_attr_or_key(usage, "completion_tokens", 0)
        return _coerce_int(prompt_tokens or 0), _coerce_int(completion_tokens or 0)

    def _build_completion_kwargs(self, prompt: str) -> dict:
        """Build provider/model-specific kwargs for chat.completions.create."""
        is_openai_gpt5_or_o = self.provider == "openai" and (
            self.model_id.startswith("gpt-5") or self.model_id.startswith("o")
        )
        kwargs = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            "timeout": self.request_timeout,
        }

        if not is_openai_gpt5_or_o:
            kwargs["temperature"] = self.temperature
        elif self.temperature != 1 and not self._temperature_warning_emitted:
            logger.warning(
                "Model %s only supports default temperature; ignoring configured value %.2f",
                self.model_id,
                self.temperature,
            )
            self._temperature_warning_emitted = True

        # OpenAI GPT-5/o-series require max_completion_tokens.
        if is_openai_gpt5_or_o:
            kwargs["max_completion_tokens"] = self.max_tokens
        else:
            kwargs["max_tokens"] = self.max_tokens
        return kwargs

    def _is_openai_gpt5_or_o(self) -> bool:
        return self.provider == "openai" and (self.model_id.startswith("gpt-5") or self.model_id.startswith("o"))

    def get_completion(self, prompt: str) -> str:
        """Get a completion from the model."""

        def _call() -> str:
            prompt_tokens_total = 0
            completion_tokens_total = 0

            kwargs = self._build_completion_kwargs(prompt)
            response = self._get_client().chat.completions.create(**kwargs)
            prompt_tokens, completion_tokens = self._extract_usage(response)
            prompt_tokens_total += prompt_tokens
            completion_tokens_total += completion_tokens
            content = self._extract_content(response)
            if content or not self._is_openai_gpt5_or_o():
                self._record_usage(prompt_tokens_total, completion_tokens_total)
                return content

            # GPT-5/o-series can return empty visible output on long prompts when
            # completion budget is too small. Retry once with a larger budget.
            fallback_kwargs = dict(kwargs)
            fallback_kwargs["max_completion_tokens"] = max(
                int(fallback_kwargs.get("max_completion_tokens", self.max_tokens)),
                800,
            )
            logger.warning(
                "Model %s returned empty output; retrying once with max_completion_tokens=%s",
                self.model_id,
                fallback_kwargs["max_completion_tokens"],
            )
            fallback_response = self._get_client().chat.completions.create(**fallback_kwargs)
            prompt_tokens, completion_tokens = self._extract_usage(fallback_response)
            prompt_tokens_total += prompt_tokens
            completion_tokens_total += completion_tokens
            self._record_usage(prompt_tokens_total, completion_tokens_total)
            return self._extract_content(fallback_response)

        return self._with_retries(_call)


class AnthropicClient(LLMClient):
    """Anthropic Claude client."""

    def __init__(
        self,
        model_id: str = "",
        system_prompt: str = "",
        temperature: float = DEFAULT_TEMPERATURE,
        request_timeout: int = 30,
    ):
        super().__init__(
            model_id=model_id,
            provider="anthropic",
            system_prompt=system_prompt,
            temperature=temperature,
            request_timeout=request_timeout,
        )
        self._client: anthropic.Anthropic | None = None

    def _get_client(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        return self._client

    @observe(as_type="generation", name="anthropic-completion")
    def get_completion(self, prompt: str) -> str:
        """Get a completion from the model."""

        def _call() -> str:
            response = self._get_client().messages.create(
                model=self.model_id,
                max_tokens=4096,
                temperature=self.temperature,
                system=self.system_prompt,
                messages=[{"role": "user", "content": prompt}],
                timeout=self.request_timeout,
            )
            usage = _get_attr_or_key(response, "usage")
            prompt_tokens = _coerce_int(_get_attr_or_key(usage, "input_tokens", 0) or 0)
            completion_tokens = _coerce_int(_get_attr_or_key(usage, "output_tokens", 0) or 0)
            self._record_usage(prompt_tokens, completion_tokens)
            if not response.content:
                return ""
            return "\n".join(block.text for block in response.content if getattr(block, "text", None)).strip()

        return self._with_retries(_call)


def get_llm_client(model_name: str, system_prompt: str = "", temperature: float = DEFAULT_TEMPERATURE) -> LLMClient:
    """Factory function to get appropriate LLM client."""
    request_timeout = 30
    spec = parse_model_name(model_name)

    if spec.provider == "anthropic":
        return AnthropicClient(
            model_id=spec.model_id,
            system_prompt=system_prompt,
            temperature=temperature,
            request_timeout=request_timeout,
        )
    if spec.provider in {"codex_cli", "claude_cli", "claude"}:
        raise NotImplementedError(f"Provider {spec.provider!r} has been removed (command injection risk)")
    if spec.provider in {"openai", "google", "openrouter", "deepseek"}:
        if spec.provider == "google":
            max_tokens = 512
        elif spec.provider == "openai":
            # GPT-5/o models often require larger completion budgets for stable structured output.
            max_tokens = 900
        else:
            max_tokens = 300
        return OpenAICompatibleClient(
            provider=spec.provider,
            model_id=spec.model_id,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            request_timeout=request_timeout,
        )
    raise NotImplementedError(f"Model {model_name} is not yet supported")
