"""Constants for llm-quest-benchmark"""
from pathlib import Path

# Model choices
MODEL_CHOICES = [
    "random_choice", # LLM Stub: selects random choice
    "gpt-4o",
    "gpt-4o-mini",
    "claude-3-5-sonnet-latest",
    "claude-3-5-haiku-latest",
    ]
DEFAULT_MODEL = "gpt-4o"

# Language choices
LANG_CHOICES = ["rus", "eng"]
DEFAULT_LANG = "rus"

# Default quest
DEFAULT_QUEST = "quests/boat.qm"

# Paths
PROMPT_TEMPLATES_DIR = Path(__file__).parent / "prompt_templates"

# Templates
STUB_TEMPLATE = "stub.jinja"
DEFAULT_TEMPLATE = "reasoning.jinja"

# Default temperature
DEFAULT_TEMPERATURE = 0.4  # Lower temperature for more focused responses

# Timeout settings (in seconds)
READABILITY_DELAY = 0.5  # Delay between steps for readability in interactive mode
DEFAULT_QUEST_TIMEOUT = 120  # Default timeout for single quest run
DEFAULT_BENCHMARK_TIMEOUT_FACTOR = 1.5  # Safety factor for benchmark timeout calculation
MAX_BENCHMARK_TIMEOUT = 7200  # Maximum benchmark timeout (2 hours)
INFINITE_TIMEOUT = 10**9  # Infinite timeout (used for interactive play)