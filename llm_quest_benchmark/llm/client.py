"""LLM client interface for different model providers"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Optional, Tuple
import os
import logging
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from openai import OpenAI
from llm_quest_benchmark.constants import (
    MODEL_ALIASES,
    MODEL_PROVIDER_CONFIG,
    DEFAULT_TEMPERATURE,
)

logger = logging.getLogger(__name__)
# Configure httpx logger to only show in debug mode
logging.getLogger("httpx").setLevel(logging.WARNING)

# Load local .env when running directly from repository root.
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env", override=False)


@dataclass(frozen=True)
class ModelSpec:
    """Normalized model specification."""

    provider: str
    model_id: str


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
    elif normalized.startswith("o"):
        provider, model_id = "openai", normalized
    elif normalized.startswith("gpt"):
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
        system_prompt: str = "",
        temperature: float = DEFAULT_TEMPERATURE,
        request_timeout: int = 30,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.8,
    ):
        self.model_id = model_id
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.request_timeout = request_timeout
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds

    @abstractmethod
    def get_completion(self, prompt: str) -> str:
        """Get a completion from the model."""
        pass

    def _with_retries(self, fn: Callable[[], str]) -> str:
        """Run an LLM request function with bounded retries and backoff."""
        last_error: Optional[Exception] = None
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
        raise RuntimeError(
            f"LLM request failed after {self.max_retries + 1} attempts: {last_error}"
        ) from last_error

    def __call__(self, prompt: str) -> str:
        """Get a completion from the model."""
        return self.get_completion(prompt)


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
            system_prompt=system_prompt,
            temperature=temperature,
            request_timeout=request_timeout,
        )
        self.provider = provider
        self.max_tokens = max_tokens
        self._client: Optional[OpenAI] = None

    def _require_api_key(self, env_var: str) -> str:
        value = os.getenv(env_var)
        if value:
            return value
        raise RuntimeError(
            f"Missing API key for provider '{self.provider}'. "
            f"Set {env_var} in your environment or .env file."
        )

    def _provider_settings(self) -> Tuple[Optional[str], Optional[str]]:
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
            kwargs = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            self._client = OpenAI(**kwargs)
        return self._client

    @staticmethod
    def _extract_content(response: Any) -> str:
        content = response.choices[0].message.content
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

    def get_completion(self, prompt: str) -> str:
        """Get a completion from the model."""
        def _call() -> str:
            response = self._get_client().chat.completions.create(
                model=self.model_id,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                timeout=self.request_timeout,
            )
            return self._extract_content(response)

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
            system_prompt=system_prompt,
            temperature=temperature,
            request_timeout=request_timeout,
        )
        self._client: Optional[anthropic.Anthropic] = None

    def _get_client(self) -> anthropic.Anthropic:
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        return self._client

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
            if not response.content:
                return ""
            return "\n".join(
                block.text for block in response.content if getattr(block, "text", None)
            ).strip()

        return self._with_retries(_call)


def get_llm_client(model_name: str, system_prompt: str = "", temperature: float = DEFAULT_TEMPERATURE) -> LLMClient:
    """Factory function to get appropriate LLM client."""
    # Use a longer request timeout to prevent timeouts during quest execution
    request_timeout = 60
    spec = parse_model_name(model_name)

    if spec.provider == "anthropic":
        return AnthropicClient(
            model_id=spec.model_id,
            system_prompt=system_prompt,
            temperature=temperature,
            request_timeout=request_timeout,
        )
    if spec.provider in {"openai", "google", "openrouter", "deepseek"}:
        max_tokens = 512 if spec.provider == "google" else 200
        return OpenAICompatibleClient(
            provider=spec.provider,
            model_id=spec.model_id,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            request_timeout=request_timeout,
        )
    raise NotImplementedError(f"Model {model_name} is not yet supported")
