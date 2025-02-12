"""LLM client interface for different model providers"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import os

from openai import OpenAI


class LLMClient(ABC):
    """Base class for LLM clients"""

    @abstractmethod
    def __call__(self, prompt: str, **kwargs) -> str:
        """Call LLM with prompt and return response"""
        pass


class OpenAIClient(LLMClient):
    """Client for OpenAI API"""

    def __init__(self, model_id: str, max_tokens: int = 200):
        self.client = OpenAI()  # Uses OPENAI_API_KEY from environment
        self.model = model_id
        self.max_tokens = max_tokens

    def __call__(self, prompt: str, **kwargs) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that responds with just a number."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=self.max_tokens,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()


def get_llm_client(model_name: str) -> LLMClient:
    """Factory function to get appropriate LLM client"""
    model_map = {
        "gpt-4o": ("gpt-4o-mini", OpenAIClient),
        "gpt-4o-mini": ("gpt-4o-mini", OpenAIClient),  # Use same model for now
        "sonnet": ("gpt-4o-mini", OpenAIClient),  # Use GPT-4 for now until we add Claude
        "deepseek": ("gpt-4o-mini", OpenAIClient),  # Use GPT-4 for now until we add DeepSeek
    }

    if model_name not in model_map:
        raise ValueError(f"Unsupported model: {model_name}")

    model_id, client_class = model_map[model_name]
    return client_class(model_id)