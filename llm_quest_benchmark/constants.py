"""Constants for llm-quest-benchmark"""
from pathlib import Path
import re

# Model choices
MODEL_CHOICES = [
    "random_choice", # LLM Stub: selects random choice
    "gpt-4o",
    "gpt-4o-mini",
    "claude-3-7-sonnet-latest",
    "claude-3-5-sonnet-latest",
    "claude-3-5-haiku-latest",
]
DEFAULT_MODEL = "gpt-4o"

# Default quest
DEFAULT_QUEST = Path("quests/kr1/Boat.qm")

# Quest search configuration
QUEST_ROOT_DIRECTORY = "quests"
RECURSIVE_QUEST_SEARCH = True  # When True, will search all subdirectories under QUEST_ROOT_DIRECTORY

# Paths
PROMPT_TEMPLATES_DIR = Path(__file__).parent / "prompt_templates"

# Templates
STUB_TEMPLATE = "stub.jinja"
DEFAULT_TEMPLATE = "reasoning.jinja"
SYSTEM_ROLE_TEMPLATE = "system_role.jinja"

# Default temperature
DEFAULT_TEMPERATURE = 0.4

# Timeout settings (in seconds)
READABILITY_DELAY = 0.5  # Delay between steps for readability in interactive mode
DEFAULT_QUEST_TIMEOUT = 120  # Default timeout for single quest run
DEFAULT_BENCHMARK_TIMEOUT_FACTOR = 1.5  # Safety factor for benchmark timeout calculation
MAX_BENCHMARK_TIMEOUT = 7200  # Maximum benchmark timeout (2 hours)
INFINITE_TIMEOUT = 10**9  # Infinite timeout (used for interactive play)

# Web server
WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = 8000

# Quest state detection patterns
# Pattern to detect credit rewards in text (e.g., "10000 cr")
CREDIT_REWARD_PATTERN = re.compile(r'(\d+)\s*cr\b')

# Common success indicators in text for quest completion
SUCCESS_INDICATORS = [
    "mission complete", 
    "mission accomplished",
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
    "успешно"
]

# Common failure indicators in text
FAILURE_INDICATORS = [
    "mission failed",
    "you died",
    "game over",
    "you lost",
    "failure",
    "failed",
    "провал",
    "миссия провалена",
    "вы погибли",
    "вы проиграли",
    "конец игры",
    "неудача"
]

# Special location IDs
SYNTHETIC_SUCCESS_LOCATION = "99"  # Used for synthetic success endings
