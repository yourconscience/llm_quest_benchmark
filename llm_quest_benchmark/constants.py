"""Constants for llm-quest-benchmark"""

import re
from pathlib import Path

# Provider registry used by parser/client factory.
MODEL_PROVIDER_CONFIG = {
    "openai": {"models": ["gpt-5", "gpt-5-mini", "gpt-5-nano", "o4-mini"]},
    "anthropic": {"models": ["claude-sonnet-4-5", "claude-opus-4-1", "claude-3-5-haiku-latest"]},
    "google": {"models": ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro"]},
    "deepseek": {"models": ["deepseek-3.2-chat", "deepseek-reasoner"]},
    "codex_cli": {"models": ["codex-exec"]},
    "claude_cli": {"models": ["claude-exec"]},
    # Claude CLI provider: accepts any model id and runs via the `claude` CLI binary.
    "claude": {"models": []},
    # Optional compatibility gateway (hidden from default UI model list).
    "openrouter": {"models": []},
}

# User-facing model choices (clean list, no duplicated provider prefixes).
MODEL_CHOICES = [
    "random_choice",
    "codex-exec",
    "claude-exec",
    # OpenAI
    "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano",
    "o4-mini",
    # Anthropic
    "claude-sonnet-4-5",
    "claude-opus-4-1",
    "claude-3-5-haiku-latest",
    # Google
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
    # DeepSeek
    "deepseek-3.2-chat",
    "deepseek-reasoner",
]

# Aliases accepted by parser for backwards compatibility.
MODEL_ALIASES = {
    # OpenAI
    "gpt-5": "openai:gpt-5",
    "gpt-5-mini": "openai:gpt-5-mini",
    "gpt-5-nano": "openai:gpt-5-nano",
    "o4-mini": "openai:o4-mini",
    "codex-exec": "codex_cli:codex-exec",
    "codex_exec": "codex_cli:codex-exec",
    # Anthropic
    "claude-sonnet-4-5": "anthropic:claude-sonnet-4-5",
    "claude-opus-4-1": "anthropic:claude-opus-4-1-20250805",
    "claude-3-5-haiku-latest": "anthropic:claude-3-5-haiku-latest",
    "claude-exec": "claude_cli:claude-exec",
    "claude_exec": "claude_cli:claude-exec",
    # Compatibility Anthropic aliases
    "claude-sonnet-4-0": "anthropic:claude-sonnet-4-20250514",
    "claude-sonnet-4-20250514": "anthropic:claude-sonnet-4-20250514",
    "claude-opus-4-1-20250805": "anthropic:claude-opus-4-1-20250805",
    # Google
    "gemini-2.5-pro": "google:gemini-2.5-pro",
    "gemini-2.5-flash": "google:gemini-2.5-flash",
    "gemini-2.5-flash-lite": "google:gemini-2.5-flash-lite",
    # DeepSeek
    "deepseek-3.2-chat": "deepseek:deepseek-chat",
    # Compatibility DeepSeek aliases
    "deepseek-chat": "deepseek:deepseek-chat",
    "deepseek-reasoner": "deepseek:deepseek-reasoner",
}

DEFAULT_MODEL = "gpt-5-mini"

# Default quest
DEFAULT_QUEST = Path("quests/Boat.qm")

# Quest search configuration
QUEST_ROOT_DIRECTORY = "quests"
RECURSIVE_QUEST_SEARCH = True  # When True, will search all subdirectories under QUEST_ROOT_DIRECTORY

# Paths
PROMPT_TEMPLATES_DIR = Path(__file__).parent / "prompt_templates"

# Templates
STUB_TEMPLATE = "stub.jinja"
DEFAULT_TEMPLATE = "reasoning.jinja"
SYSTEM_ROLE_TEMPLATE = "system_role.jinja"


def normalize_template_name(template_name: str) -> str:
    """Normalize template identifiers so CLI/YAML can omit the .jinja suffix."""
    normalized = (template_name or "").strip()
    if not normalized:
        return normalized
    if Path(normalized).suffix:
        return normalized
    return f"{normalized}.jinja"


# Default temperature
DEFAULT_TEMPERATURE = 0.4

# Timeout settings (in seconds)
READABILITY_DELAY = 0.5  # Delay between steps for readability in interactive mode
DEFAULT_QUEST_TIMEOUT = 120  # Default timeout for single quest run
DEFAULT_BENCHMARK_TIMEOUT_FACTOR = 1.5  # Safety factor for benchmark timeout calculation
MAX_BENCHMARK_TIMEOUT = 7200  # Maximum benchmark timeout (2 hours)
INFINITE_TIMEOUT = 10**9  # Infinite timeout (used for interactive play)

# Quest state detection patterns
# Pattern to detect credit rewards in text (e.g., "10000 cr", "10000 credits")
CREDIT_REWARD_PATTERN = re.compile(r"(\d+)\s*(?:cr(?:edits?)?)\b")

# Common success indicators in text for quest completion
# NOTE: order matters - failure indicators are checked first in detect_quest_outcome
# to avoid false positives like "mission completely failed" matching "mission complete"
SUCCESS_INDICATORS = [
    "mission accomplished",
    "mission is complete",
    "succeeded",
    "successful",
    "congratulations",
    "you won",
    "you succeeded",
    "victory",
    "mission success",
    "вы успешно",
    "задание выполнено",
    "получите",
    "награда",
    "спасибо",
    "поздравляем",
    "успешно",
]

# Common failure indicators in text
FAILURE_INDICATORS = [
    "mission failed",
    "mission completely",
    "you died",
    "game over",
    "you lost",
    "you failed",
    "failure",
    "failed",
    "провал",
    "миссия провалена",
    "вы погибли",
    "вы проиграли",
    "конец игры",
    "неудача",
]

# Special location IDs
SYNTHETIC_SUCCESS_LOCATION = "99"  # Used for synthetic success endings
