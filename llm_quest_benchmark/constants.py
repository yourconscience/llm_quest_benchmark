"""Constants for llm-quest-benchmark"""
from pathlib import Path

# Model choices
MODEL_CHOICES = ["gpt-4o", "gpt-4o-mini", "sonnet", "deepseek"]
DEFAULT_MODEL = "gpt-4o"

# Language choices
LANG_CHOICES = ["rus", "eng"]
DEFAULT_LANG = "rus"

# Default quest
DEFAULT_QUEST = "quests/boat.qm"

# Paths
PROMPT_TEMPLATES_DIR = Path(__file__).parent / "prompt_templates"

# Templates
DEFAULT_TEMPLATE = "default.jinja"
REASONING_TEMPLATE = "reasoning.jinja"

# Default temperature
DEFAULT_TEMPERATURE = 0.3  # Lower temperature for more focused responses