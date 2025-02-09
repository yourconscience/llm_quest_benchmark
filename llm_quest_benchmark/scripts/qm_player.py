"""
Interactive Space Rangers quests console player with rich terminal output
"""

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

from llm_quest_benchmark.constants import PROJECT_ROOT
from llm_quest_benchmark.renderers.terminal import TerminalRenderer
from llm_quest_benchmark.utils.text_processor import process_game_state


def find_node_executable() -> str:
    """Find the node executable in PATH or common locations"""
    node_path = shutil.which("node")
    if node_path:
        return node_path

    common_paths = [
        "/usr/local/bin/node",
        "/usr/bin/node",
        "/opt/homebrew/bin/node",  # macOS
    ]
    for path in common_paths:
        if os.path.isfile(path):
            return path

    raise FileNotFoundError(
        "Could not find node executable. Install Node.js and ensure it's in PATH.")


def play_quest(quest_path: str, language: str):
    """Play quest in interactive mode using TypeScript console player"""
    renderer = TerminalRenderer()

    ts_path = PROJECT_ROOT / "space-rangers-quest"
    if not ts_path.exists():
        raise FileNotFoundError("Space Rangers submodule not found")

    quest_path = Path(quest_path).resolve()
    if not quest_path.exists():
        raise FileNotFoundError(f"Quest file not found: {quest_path}")

    node_exe = find_node_executable()
    consoleplayer_path = PROJECT_ROOT / "llm_quest_benchmark" / "scripts" / "consoleplayer.ts"

    cmd = [
        node_exe,
        "-r",
        "ts-node/register",
        str(consoleplayer_path),
        str(quest_path),
    ]

    try:
        process = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            env={
                **os.environ, "LANG": language
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                try:
                    raw_state = json.loads(line.strip())
                    game_state = process_game_state(raw_state)
                    renderer.render_game_state(game_state)
                except json.JSONDecodeError:
                    renderer.render_error(f"Invalid game state: {line.strip()}")

        if process.returncode != 0:
            stderr = process.stderr.read()
            if stderr:
                renderer.render_error(stderr)

    except KeyboardInterrupt:
        process.terminate()
        renderer.render_error("Quest aborted by user")
    except Exception as e:
        renderer.render_error(f"Unexpected error: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(
        description="Run Space Rangers quest interactively",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("quest_path", help="Path to the .qm file")
    parser.add_argument(
        "--lang",
        choices=["rus", "eng"],
        default="rus",
        help="Language for quest text (default: rus)",
    )
    args = parser.parse_args()

    renderer = TerminalRenderer()
    renderer.render_title()
    play_quest(args.quest_path, args.lang)


if __name__ == "__main__":
    main()
