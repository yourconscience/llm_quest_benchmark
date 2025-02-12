"""
LLM client implementations for different providers
"""
from abc import ABC, abstractmethod
import os
from typing import List, Dict, Any, Optional
from openai import OpenAI
import anthropic
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """Standardized response from any LLM provider"""
    content: str
    model: str
    usage: Optional[Dict[str, int]] = None
    raw_response: Any = None


class LLMClientError(Exception):
    """Base exception for LLM client errors"""
    pass


class BaseLLMClient(ABC):
    """Base class for LLM clients"""

    @abstractmethod
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        max_tokens: int = 200,
        temperature: float = 0.7,
        stop: Optional[List[str]] = None,
    ) -> LLMResponse:
        """Generate chat completion"""
        pass


class OpenAIClient(BaseLLMClient):
    """Native OpenAI client"""

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise LLMClientError("OPENAI_API_KEY environment variable not set")
        self.client = OpenAI(api_key=api_key)

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4",
        max_tokens: int = 200,
        temperature: float = 0.7,
        stop: Optional[List[str]] = None,
    ) -> LLMResponse:
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=stop
            )
            return LLMResponse(
                content=response.choices[0].message.content,
                model=model,
                usage=response.usage._asdict() if hasattr(response, 'usage') else None,
                raw_response=response
            )
        except Exception as e:
            raise LLMClientError(f"OpenAI API error: {str(e)}")


class AnthropicClient(BaseLLMClient):
    """Native Anthropic client"""

    MODEL_MAPPING = {
        "anthropic/claude-3-sonnet": "claude-3-sonnet-20240229",
        "anthropic/claude-3-opus": "claude-3-opus-20240229",
        "anthropic/claude-2": "claude-2.1",
    }

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise LLMClientError("ANTHROPIC_API_KEY environment variable not set")
        self.client = anthropic.Anthropic(api_key=api_key)

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "claude-3-sonnet-20240229",
        max_tokens: int = 200,
        temperature: float = 0.7,
        stop: Optional[List[str]] = None,
    ) -> LLMResponse:
        try:
            # Map OpenRouter model name to Anthropic model name
            if model.startswith("anthropic/"):
                model = self.MODEL_MAPPING.get(model)
                if not model:
                    raise LLMClientError(f"Unknown Anthropic model: {model}")

            # Convert messages to Anthropic format
            system = next((m["content"] for m in messages if m["role"] == "system"), None)
            prompt = next(m["content"] for m in messages if m["role"] == "user")

            response = self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                stop_sequences=stop
            )
            return LLMResponse(
                content=response.content[0].text,
                model=model,
                usage=None,  # Anthropic doesn't provide token usage
                raw_response=response
            )
        except Exception as e:
            raise LLMClientError(f"Anthropic API error: {str(e)}")


class OpenRouterClient(BaseLLMClient):
    """OpenRouter client using OpenAI's client"""

    def __init__(self):
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise LLMClientError("OPENROUTER_API_KEY environment variable not set")
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://github.com/LeonGuertler/TextArena",
                "X-Title": "LLM Quest Benchmark"
            }
        )

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "anthropic/claude-3-sonnet",
        max_tokens: int = 200,
        temperature: float = 0.7,
        stop: Optional[List[str]] = None,
    ) -> LLMResponse:
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=stop
            )
            return LLMResponse(
                content=response.choices[0].message.content,
                model=model,
                usage=response.usage._asdict() if hasattr(response, 'usage') else None,
                raw_response=response
            )
        except Exception as e:
            raise LLMClientError(f"OpenRouter API error: {str(e)}")