"""Test the new quest registry system"""
import logging
from pathlib import Path
import sys

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the project root to Python path to ensure imports work
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from llm_quest_benchmark.core.quest_registry import get_registry, resolve_quest_paths
from llm_quest_benchmark.web.utils.errors import validate_quest_file, QuestNotFoundError


def test_registry():
    """Test the registry functionality"""
    # Initialize registry
    logger.info("Initializing quest registry...")
    registry = get_registry(reset_cache=True)

    # Get all quests
    all_quests = registry.get_all_quests()
    logger.info(f"Found {len(all_quests)} quest files")
    logger.info(f"First few quests: {all_quests[:3]}")

    # Get unique quests
    unique_quests = registry.get_unique_quests()
    logger.info(f"Found {len(unique_quests)} unique quest files")

    # Check duplicates
    duplicates = [q for q in all_quests if q.is_duplicate]
    logger.info(f"Found {len(duplicates)} duplicate quest files")
    if duplicates:
        logger.info(
            f"First duplicate: {duplicates[0].path} is duplicate of {duplicates[0].duplicate_of}")

    # Test resolving various path patterns
    test_paths = [
        "quests/Boat.qm",
        "quests/kr1/Boat.qm",
        "quests/kr2_en",
        "quests/kr1",
        "quests/*.qm",
        "quests/kr2_en/*.qm",
        "nonexistent_dir",
    ]

    logger.info("\nTesting path resolution:")
    for path in test_paths:
        try:
            resolved = registry.resolve_quest_path(path)
            logger.info(f"Path: {path} -> {len(resolved)} files")
            if resolved:
                logger.info(f"  First resolved: {resolved[0]}")
        except Exception as e:
            logger.error(f"Path: {path} -> Error: {e}")

    # Test web validation
    logger.info("\nTesting web validation:")
    for path in test_paths:
        try:
            validate_quest_file(path)
            logger.info(f"Path: {path} -> Valid")
        except QuestNotFoundError as e:
            logger.warning(f"Path: {path} -> Invalid: {e}")
        except Exception as e:
            logger.error(f"Path: {path} -> Error: {type(e).__name__}: {str(e)}")


if __name__ == "__main__":
    test_registry()
