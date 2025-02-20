"""LLM client interface for different model providers"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import os
import logging
import anthropic

from openai import OpenAI
from llm_quest_benchmark.constants import MODEL_CHOICES, DEFAULT_TEMPERATURE

logger = logging.getLogger(__name__)
# Configure httpx logger to only show in debug mode
logging.getLogger("httpx").setLevel(logging.WARNING)


class LLMClient(ABC):
    """Base class for LLM clients"""

    def __init__(self, model_id: str = "", system_prompt: str = "", temperature: float = DEFAULT_TEMPERATURE):
        """Initialize the LLM client.

        Args:
            model_id (str, optional): ID of the model to use. Defaults to "".
            system_prompt (str, optional): System prompt to use. Defaults to "".
            temperature (float, optional): Temperature parameter for sampling. Defaults to DEFAULT_TEMPERATURE.
        """
        self.model_id = model_id
        self.system_prompt = system_prompt
        self.temperature = temperature

    @abstractmethod
    def get_completion(self, prompt: str) -> str:
        """Get a completion from the model.

        Args:
            prompt (str): The prompt to complete

        Returns:
            str: The completion
        """
        pass

    def __call__(self, prompt: str) -> str:
        """Get a completion from the model.

        Args:
            prompt (str): The prompt to complete

        Returns:
            str: The completion
        """
        return self.get_completion(prompt)


class OpenAIClient(LLMClient):
    """Client for OpenAI API"""

    def __init__(self, model_id: str = "", system_prompt: str = "", temperature: float = DEFAULT_TEMPERATURE, max_tokens: int = 200):
        """Initialize the OpenAI client.

        Args:
            model_id (str, optional): ID of the model to use. Defaults to "".
            system_prompt (str, optional): System prompt to use. Defaults to "".
            temperature (float, optional): Temperature parameter for sampling. Defaults to DEFAULT_TEMPERATURE.
            max_tokens (int, optional): Maximum tokens to generate. Defaults to 200.
        """
        super().__init__(model_id=model_id, system_prompt=system_prompt, temperature=temperature)
        self.client = OpenAI()  # Uses OPENAI_API_KEY from environment
        self.max_tokens = max_tokens

    def get_completion(self, prompt: str) -> str:
        """Get a completion from the model.

        Args:
            prompt (str): The prompt to complete

        Returns:
            str: The completion
        """
        response = self.client.chat.completions.create(
            model=self.model_id,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            max_tokens=self.max_tokens,
            temperature=self.temperature
        )
        return response.choices[0].message.content.strip()


class AnthropicClient(LLMClient):
    """Anthropic Claude client."""

    def __init__(self, model_id: str = "", system_prompt: str = "", temperature: float = DEFAULT_TEMPERATURE):
        """Initialize the Anthropic client.

        Args:
            model_id (str, optional): ID of the model to use. Defaults to "".
            system_prompt (str, optional): System prompt to use. Defaults to "".
            temperature (float, optional): Temperature parameter for sampling. Defaults to DEFAULT_TEMPERATURE.
        """
        super().__init__(model_id=model_id, system_prompt=system_prompt, temperature=temperature)
        self.client = anthropic.Client(api_key=os.getenv("ANTHROPIC_API_KEY"))

    def get_completion(self, prompt: str) -> str:
        """Get a completion from the model.

        Args:
            prompt (str): The prompt to complete

        Returns:
            str: The completion
        """
        try:
            response = self.client.messages.create(
                model=self.model_id,
                max_tokens=4096,
                temperature=self.temperature,
                system=self.system_prompt,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Error getting completion from Anthropic: {e}")
            raise


def get_llm_client(model_name: str, system_prompt: str = "", temperature: float = DEFAULT_TEMPERATURE) -> LLMClient:
    """Factory function to get appropriate LLM client.

    Args:
        model_name (str): Name of the model to use
        system_prompt (str, optional): System prompt to use. Defaults to "".
        temperature (float, optional): Temperature parameter for sampling. Defaults to DEFAULT_TEMPERATURE.

    Returns:
        LLMClient: The LLM client

    Raises:
        NotImplementedError: If the model is not yet supported
    """
    if model_name.startswith("claude"):
        return AnthropicClient(
            model_id=model_name,
            system_prompt=system_prompt,
            temperature=temperature
        )
    elif model_name.startswith("gpt"):
        return OpenAIClient(
            model_id=model_name,
            system_prompt=system_prompt,
            temperature=temperature
        )
    else:
        raise NotImplementedError(f"Model {model_name} is not yet supported")