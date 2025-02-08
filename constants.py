"""Project-wide constants and paths"""
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent
PROMPT_TEMPLATES_DIR = PROJECT_ROOT / "llm_quest_benchmark" / "prompt_templates"
QUESTS_DIR = PROJECT_ROOT / "quests"

# Default quest for testing
DEFAULT_QUEST = QUESTS_DIR / "boat.qm"