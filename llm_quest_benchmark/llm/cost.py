"""LLM cost estimation via OpenRouter live pricing API."""

import json
import logging
import os
import urllib.request
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


@dataclass
class UsageStats:
    """Token/cost usage metadata for one request or aggregated session."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
        }


_openrouter_pricing_cache: dict[str, tuple[float, float]] | None = None


def _fetch_openrouter_pricing() -> dict[str, tuple[float, float]]:
    """Fetch per-model pricing from OpenRouter API. Returns {model_id: (input_per_M, output_per_M)}."""
    global _openrouter_pricing_cache
    if _openrouter_pricing_cache is not None:
        return _openrouter_pricing_cache

    try:
        req = urllib.request.Request(
            OPENROUTER_MODELS_URL,
            headers={"User-Agent": "llm-quest-benchmark"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        result: dict[str, tuple[float, float]] = {}
        for model in data.get("data", []):
            pricing = model.get("pricing") or {}
            prompt = pricing.get("prompt")
            completion = pricing.get("completion")
            if prompt is not None and completion is not None:
                result[model["id"]] = (
                    float(prompt) * 1_000_000,
                    float(completion) * 1_000_000,
                )
        _openrouter_pricing_cache = result
        logger.debug("Fetched pricing for %d models from OpenRouter", len(result))
        return result
    except Exception:
        logger.debug("Failed to fetch OpenRouter pricing, will return None for costs")
        _openrouter_pricing_cache = {}
        return {}


def _sanitize_env_key_fragment(raw: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in raw.upper()).strip("_")


def resolve_token_pricing(provider: str, model_id: str) -> tuple[float, float] | None:
    """Resolve per-million-token pricing. Checks env vars, then OpenRouter API."""
    provider_key = _sanitize_env_key_fragment(provider)
    model_key = _sanitize_env_key_fragment(model_id)

    # 1. Env var overrides (highest priority)
    model_input = os.getenv(f"LLM_PRICE_{provider_key}_{model_key}_INPUT_PER_M")
    model_output = os.getenv(f"LLM_PRICE_{provider_key}_{model_key}_OUTPUT_PER_M")
    if model_input is not None and model_output is not None:
        return float(model_input), float(model_output)

    default_input = os.getenv(f"LLM_PRICE_{provider_key}_DEFAULT_INPUT_PER_M")
    default_output = os.getenv(f"LLM_PRICE_{provider_key}_DEFAULT_OUTPUT_PER_M")
    if default_input is not None and default_output is not None:
        return float(default_input), float(default_output)

    # 2. OpenRouter live pricing
    or_pricing = _fetch_openrouter_pricing()

    # OpenRouter provider: model_id is "provider/model" directly
    if provider == "openrouter" and "/" in model_id and model_id in or_pricing:
        return or_pricing[model_id]

    # Direct provider: try "provider/model_id" as OpenRouter key
    or_key = f"{provider}/{model_id}"
    if or_key in or_pricing:
        return or_pricing[or_key]

    return None


def estimate_cost_usd(
    provider: str,
    model_id: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float | None:
    """Estimate cost in USD for a given number of tokens."""
    pricing = resolve_token_pricing(provider, model_id)
    if pricing is None:
        return None
    input_per_m, output_per_m = pricing
    return (prompt_tokens / 1_000_000) * input_per_m + (completion_tokens / 1_000_000) * output_per_m
