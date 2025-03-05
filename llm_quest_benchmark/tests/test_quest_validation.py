"""Test the validate_quest_file function with various path types"""
from pathlib import Path
from llm_quest_benchmark.web.utils.errors import validate_quest_file, QuestNotFoundError


def test_paths():
    """Test various path types to ensure our validation works correctly"""
    paths_to_test = [
        # File paths
        "quests/Boat.qm",  # Existing file
        "quests/nonexistent.qm",  # Non-existent file

        # Directory paths
        "quests",  # Existing directory
        "quests/kr2_eng",  # Directory to test
        "nonexistent_dir",  # Non-existent directory

        # Glob patterns
        "quests/*.qm",  # Glob pattern
        "quests/kr2_eng/*.qm"  # Directory + glob pattern
    ]

    results = {}

    for path in paths_to_test:
        try:
            validate_quest_file(path)
            results[path] = "Valid"
        except QuestNotFoundError as e:
            results[path] = f"Invalid: {str(e)}"
        except Exception as e:
            results[path] = f"Error: {type(e).__name__}: {str(e)}"

    # Print results
    for path, result in results.items():
        print(f"Path: {path}")
        print(f"  Result: {result}")
        print(f"  Exists: {Path(path).exists()}")
        if Path(path).exists():
            print(f"  Is file: {Path(path).is_file()}")
            print(f"  Is dir: {Path(path).is_dir()}")
        print()


if __name__ == "__main__":
    test_paths()
