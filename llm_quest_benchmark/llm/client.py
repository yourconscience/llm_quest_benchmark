"""LLM client interface for different model providers"""
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import anthropic
from openai import OpenAI

from llm_quest_benchmark.constants import DEFAULT_TEMPERATURE, MODEL_CHOICES

logger = logging.getLogger(__name__)
# Configure httpx logger to only show in debug mode
logging.getLogger("httpx").setLevel(logging.WARNING)


class LLMClient(ABC):
    """Base class for LLM clients"""

    def __init__(self,
                 model_id: str = "",
                 system_prompt: str = "",
                 temperature: float = DEFAULT_TEMPERATURE,
                 request_timeout: int = 30):
        self.model_id = model_id
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.request_timeout = request_timeout

    @abstractmethod
    def get_completion(self, prompt: str) -> str:
        """Get a completion from the model."""
        pass

    def __call__(self, prompt: str) -> str:
        """Get a completion from the model."""
        return self.get_completion(prompt)


class OpenAIClient(LLMClient):
    """Client for OpenAI API"""

    def __init__(self,
                 model_id: str = "",
                 system_prompt: str = "",
                 temperature: float = DEFAULT_TEMPERATURE,
                 max_tokens: int = 200,
                 request_timeout: int = 30):
        super().__init__(model_id=model_id,
                         system_prompt=system_prompt,
                         temperature=temperature,
                         request_timeout=request_timeout)
        self.client = OpenAI()  # Uses OPENAI_API_KEY from environment
        self.max_tokens = max_tokens

    def get_completion(self, prompt: str) -> str:
        """Get a completion from the model."""
        response = self.client.chat.completions.create(model=self.model_id,
                                                       messages=[{
                                                           "role": "system",
                                                           "content": self.system_prompt
                                                       }, {
                                                           "role": "user",
                                                           "content": prompt
                                                       }],
                                                       max_tokens=self.max_tokens,
                                                       temperature=self.temperature,
                                                       timeout=self.request_timeout)
        return response.choices[0].message.content.strip()


class AnthropicClient(LLMClient):
    """Anthropic Claude client."""

    def __init__(self,
                 model_id: str = "",
                 system_prompt: str = "",
                 temperature: float = DEFAULT_TEMPERATURE,
                 request_timeout: int = 30):
        super().__init__(model_id=model_id,
                         system_prompt=system_prompt,
                         temperature=temperature,
                         request_timeout=request_timeout)
        self.client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY from environment

    def get_completion(self, prompt: str) -> str:
        """Get a completion from the model."""
        try:
            response = self.client.messages.create(model=self.model_id,
                                                   max_tokens=4096,
                                                   temperature=self.temperature,
                                                   system=self.system_prompt,
                                                   messages=[{
                                                       "role": "user",
                                                       "content": prompt
                                                   }])
            return response.content[0].text
        except Exception as e:
            logger.error(f"Error getting completion from Anthropic: {e}")
            raise


def get_llm_client(model_name: str,
                   system_prompt: str = "",
                   temperature: float = DEFAULT_TEMPERATURE) -> LLMClient:
    """Factory function to get appropriate LLM client."""
    # Use a longer request timeout to prevent timeouts during quest execution
    request_timeout = 60

    if model_name.startswith("claude"):
        return AnthropicClient(model_id=model_name,
                               system_prompt=system_prompt,
                               temperature=temperature,
                               request_timeout=request_timeout)
    elif model_name.startswith("gpt"):
        return OpenAIClient(model_id=model_name,
                            system_prompt=system_prompt,
                            temperature=temperature,
                            request_timeout=request_timeout)
    else:
        raise NotImplementedError(f"Model {model_name} is not yet supported")
