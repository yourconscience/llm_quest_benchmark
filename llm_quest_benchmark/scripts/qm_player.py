"""
Interactive Space Rangers quests console player
"""

import subprocess
import argparse
import os
import shutil
from pathlib import Path
from llm_quest_benchmark.constants import PROJECT_ROOT

def find_node_executable() -> str:
    """Find the node executable in PATH or common locations"""
    # First try to find node in PATH
    node_path = shutil.which("node")
    if node_path:
        return node_path

    # Common locations for node
    common_paths = [
        "/usr/local/bin/node",
        "/usr/bin/node",
        "/opt/homebrew/bin/node",  # Common on macOS
    ]
    for path in common_paths:
        if os.path.isfile(path):
            return path

    raise FileNotFoundError(
        "Could not find node executable. Ensure Node.js is installed and in PATH."
    )

def play_quest(quest_path: str):
    """Play quest in interactive mode using TypeScript console player"""
    ts_path = PROJECT_ROOT / "space-rangers-quest"
    if not ts_path.exists():
        raise FileNotFoundError("Space Rangers submodule not found")

    # Ensure quest path exists
    quest_path = Path(quest_path).resolve()
    if not quest_path.exists():
        raise FileNotFoundError(f"Quest file not found: {quest_path}")

    # Get full path to node executable
    node_exe = find_node_executable()

    # Update consoleplayer.ts path
    consoleplayer_path = PROJECT_ROOT / "llm_quest_benchmark" / "scripts" / "consoleplayer.ts"

    cmd = [
        node_exe,  # Use full path to node
        "-r", "ts-node/register",
        str(consoleplayer_path),
        str(quest_path)
    ]

    # Run TypeScript process and connect it directly to terminal
    try:
        process = subprocess.Popen(
            cmd,
            cwd=".",  # Run from our project root
            env={
                **os.environ,  # Include current environment
                "LANG": "rus"  # Set language for QMPlayer
            }
        )
        process.wait()
    except KeyboardInterrupt:
        process.terminate()
        print("\nQuest aborted by user")
    except subprocess.CalledProcessError as e:
        print(f"\nError running quest: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description="Run Space Rangers quest interactively")
    parser.add_argument("quest_path", help="Path to the .qm file")
    args = parser.parse_args()

    play_quest(args.quest_path)


if __name__ == "__main__":
    main()
