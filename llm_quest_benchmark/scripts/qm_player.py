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
                "QM_LANG": language,
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
        quest_completed = False

        # Store the last valid state for fallback
        last_valid_state = None
        final_state = None
        final_reward = 0

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
                    last_valid_state = raw_state  # Store last valid state
                    step_count += 1
                    # Check for game end condition
                    if raw_state.get('gameEnded') or not raw_state.get('choices'):
                        renderer.console.print("\n[bold green]Quest ended![/bold green]\n")
                        final_state = raw_state  # Store final state
                        quest_completed = True
                        game_active = False
                        break

                    game_state = process_game_state(raw_state)
                    choice_mapper = ChoiceMapper(raw_state['choices'])
                    renderer.render_game_state(game_state)

                    # Get user input and send to process
                    jump_id = renderer.prompt_choice(choice_mapper, skip)
                    process.stdin.write(f"{jump_id}\n")
                    process.stdin.flush()

                    # Revert to working version: log the step with default reward 0
                    metrics_logger.log_step(step_count, raw_state, action=str(jump_id), reward=0)
                    # Continue game flow as managed by the TypeScript subprocess

                elif line.startswith('Wrong input'):
                    renderer.render_error("Invalid choice! Please try again.")
                else:
                    print(line)

            except json.JSONDecodeError:
                renderer.render_error(f"Failed to parse game state")

        # Try to get final state from different sources
        try:
            # First try: Parse the last line if it looks like JSON
            if line and line.strip().startswith('{'):
                try:
                    parsed_state = json.loads(line)
                    if parsed_state.get('gameEnded', False):
                        final_state = parsed_state
                except json.JSONDecodeError:
                    pass

            # Second try: Use the stored final state from the game loop
            if not final_state and last_valid_state:
                final_state = last_valid_state

            # Extract reward and status
            if final_state:
                final_reward = final_state.get("finalReward", 0)
                completed = final_state.get("completed", False)
                timed_out = final_state.get("debugInfo", {}).get("timeOut", False)

                # Debug output for verification
                renderer.console.print(f"\n[dim]Final state summary:[/dim]")
                renderer.console.print(f"[dim]Completed: {completed}[/dim]")
                renderer.console.print(f"[dim]Final Reward: {final_reward}[/dim]")
                renderer.console.print(f"[dim]Time Out: {timed_out}[/dim]")
            else:
                renderer.render_error("No valid final state found, using default values")
                final_reward = 0
                final_state = last_valid_state or {}

        except Exception as e:
            renderer.console.print("[dim]Failed to process final state[/dim]")
            renderer.render_error(f"Error processing final state: {e}")
            final_reward = 0
            final_state = last_valid_state or {}

        # Cleanup after loop exits
        if process.poll() is None:
            process.terminate()
        stderr = process.stderr.read()
        if process.returncode != 0 and stderr:
            renderer.render_error(f"Process error: {stderr}")

        # Update the completion message based on the final state
        if final_reward > 0 or final_state.get("completed", False):
            renderer.console.print("\n[bold green]🎉 Quest completed successfully![/bold green]\n")
        else:
            renderer.console.print("\n[bold red]🚫 Quest failed or ended prematurely![/bold red]\n")

        metrics_logger.log_step(step_count + 1, final_state, action="final", reward=final_reward)

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
