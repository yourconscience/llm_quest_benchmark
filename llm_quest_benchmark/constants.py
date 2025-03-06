"""Constants for llm-quest-benchmark"""
import re
from enum import Enum, auto
from pathlib import Path

# Model choices
MODEL_CHOICES = [
    "random_choice",  # LLM Stub: selects random choice
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
SYSTEM_TEMPLATES_DIR = PROMPT_TEMPLATES_DIR / "system"
ACTION_TEMPLATES_DIR = PROMPT_TEMPLATES_DIR / "action"

# Templates
STUB_TEMPLATE = "action/stub.jinja"
DEFAULT_TEMPLATE = "action/reasoning.jinja"
SYSTEM_ROLE_TEMPLATE = "system/system_role.jinja"

# Create template directories if they don't exist
SYSTEM_TEMPLATES_DIR.mkdir(exist_ok=True, parents=True)
ACTION_TEMPLATES_DIR.mkdir(exist_ok=True, parents=True)

# Default temperature
DEFAULT_TEMPERATURE = 0.7  # Balance between focused results and exploration

# Timeout settings (in seconds)
READABILITY_DELAY = 0.5  # Delay between steps for readability in interactive mode
DEFAULT_QUEST_TIMEOUT = 120  # Default timeout for single quest run
DEFAULT_BENCHMARK_TIMEOUT_FACTOR = 1.5  # Safety factor for benchmark timeout calculation
MAX_BENCHMARK_TIMEOUT = 7200  # Maximum benchmark timeout (2 hours)
INFINITE_TIMEOUT = 10**9  # Infinite timeout (used for interactive play)

# Web server
WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = 8000

# Memory types
MEMORY_TYPES = ["message_history", "summary"]
DEFAULT_MEMORY_TYPE = "message_history"
DEFAULT_MEMORY_MAX_HISTORY = 10


# Agent tools
class ToolType(str, Enum):
    """Available tools for agents"""
    CALCULATOR = "calculator"


# Tool implementations
CALCULATOR_TOOL_IMPLEMENTATION = """
def calculator(expression: str) -> str:
    \"\"\"Evaluates a mathematical expression and returns the result.

    Args:
        expression: A string containing a mathematical expression (e.g., "2 + 3 * 4")

    Returns:
        The result of the evaluation as a string
    \"\"\"
    try:
        # Safely evaluate the expression
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"Error: {str(e)}"
"""

# Quest state detection patterns
# Pattern to detect credit rewards in text (e.g., "10000 cr")
CREDIT_REWARD_PATTERN = re.compile(r'(\d+)\s*cr\b')

# Common success indicators in text for quest completion
SUCCESS_INDICATORS = [
    "mission complete", "mission accomplished", "succeeded", "successful", "congratulations",
    "you won", "you succeeded", "victory", "mission success", "вы успешно", "задание выполнено",
    "получите", "награда", "спасибо", "поздравляем", "успешно"
]

# Common failure indicators in text
FAILURE_INDICATORS = [
    "mission failed", "you died", "game over", "you lost", "failure", "failed", "провал",
    "миссия провалена", "вы погибли", "вы проиграли", "конец игры", "неудача"
]

# Special location IDs
SYNTHETIC_SUCCESS_LOCATION = "99"  # Used for synthetic success endings
