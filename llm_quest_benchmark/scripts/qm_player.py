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
from llm_quest_benchmark.utils.choice_mapper import ChoiceMapper
from llm_quest_benchmark.metrics import MetricsLogger


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


def play_quest(quest_path: str, language: str, skip: bool = False, metrics: bool = False):
    """Play quest in interactive mode using TypeScript console player"""
    renderer = TerminalRenderer()
    metrics_logger = MetricsLogger(auto_save=metrics)
    if metrics:
        metrics_logger.set_quest_file(str(quest_path))

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
                **os.environ,
                "LANG": language,
                "NODE_PATH": str(ts_path / "node_modules")
            },
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )

        # Read and process stdout line by line
        game_active = True
        step_count = 0

        while game_active and process.poll() is None:
            line = process.stdout.readline()
            if not line:
                break

            line = line.strip()
            if not line:
                continue

            try:
                if line.startswith('{'):
                    raw_state = json.loads(line)
                    step_count += 1
                    metrics_logger.log_step(
                        step=step_count,
                        state=raw_state,
                        action="",  # No agent action in interactive mode
                        reward=0,
                    )
                    # Check for game end condition
                    if raw_state.get('gameEnded') or not raw_state.get('choices'):
                        renderer.console.print("\n[bold green]🎉 Quest completed![/bold green]\n")
                        game_active = False
                        break

                    game_state = process_game_state(raw_state)
                    choice_mapper = ChoiceMapper(raw_state['choices'])
                    renderer.render_game_state(game_state)

                    # Get user input and send to process
                    jump_id = renderer.prompt_choice(choice_mapper, skip)
                    process.stdin.write(f"{jump_id}\n")
                    process.stdin.flush()

                elif line.startswith('Wrong input'):
                    renderer.render_error("Invalid choice! Please try again.")
                else:
                    print(line)

            except json.JSONDecodeError:
                renderer.render_error(f"Failed to parse game state")

        # Cleanup after loop exits
        if process.poll() is None:
            process.terminate()

        if process.returncode != 0:
            stderr = process.stderr.read()
            if stderr:
                renderer.render_error(f"Process error: {stderr}")

        if metrics:
            saved_path = metrics_logger.save()
            if saved_path:
                renderer.console.print(f"\n[dim]Metrics saved to: {saved_path}[/dim]")

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
