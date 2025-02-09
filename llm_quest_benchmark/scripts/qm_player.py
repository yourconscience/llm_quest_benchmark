"""
Interactive Space Rangers quests console player with rich terminal output
"""

import subprocess
import argparse
import os
import shutil
import json
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from rich.table import Table
from llm_quest_benchmark.constants import PROJECT_ROOT

# Initialize rich console
console = Console()

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

def format_game_state(state_json: str) -> None:
    """Format and display the game state using rich"""
    try:
        state = json.loads(state_json)

        # Display the quest text in a panel
        console.print(Panel(
            state['text'],
            title="Quest",
            border_style="blue",
            padding=(1, 2)
        ))

        # Display parameters if any exist
        if state['paramsState']:
            param_table = Table(title="Parameters", show_header=True, header_style="bold magenta")
            param_table.add_column("Parameter", style="cyan")
            param_table.add_column("Value", style="green")

            for param in state['paramsState']:
                param_table.add_row(str(param['name']), str(param['value']))

            console.print(param_table)
            console.print()

        # Display choices in a numbered list
        if state['choices']:
            choices_panel = Table.grid(padding=1)
            choices_panel.add_column(style="yellow", justify="right")
            choices_panel.add_column(style="white")

            for i, choice in enumerate(state['choices'], 1):
                # Only show active choices
                if choice.get('active', True):
                    choices_panel.add_row(
                        f"{i}.",
                        choice['text']
                    )

            console.print(Panel(
                choices_panel,
                title="Available Actions",
                border_style="green",
                padding=(1, 2)
            ))

    except json.JSONDecodeError:
        # If we can't parse the JSON, just print it raw
        console.print(state_json)

def play_quest(quest_path: str, language: str):
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

    # Use the CUSTOM consoleplayer.ts in the llm_quest_benchmark/scripts directory
    consoleplayer_path = PROJECT_ROOT / "llm_quest_benchmark" / "scripts" / "consoleplayer.ts"

    cmd = [
        node_exe,
        "-r", "ts-node/register",
        str(consoleplayer_path),
        str(quest_path)  # Pass the quest file path
    ]

    try:
        process = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT), # Run from the PROJECT_ROOT
            env={**os.environ, "LANG": language},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,  # Get string output instead of bytes
            bufsize=1,  # Line buffered
            universal_newlines=True
        )

        # Process output line by line
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                format_game_state(line.strip())

        # Check for any errors
        if process.returncode != 0:
            stderr = process.stderr.read()
            if stderr:
                console.print(f"[red]Error:[/red] {stderr}")

    except KeyboardInterrupt:
        process.terminate()
        console.print("\n[yellow]Quest aborted by user[/yellow]")
    except subprocess.CalledProcessError as e:
        console.print(f"\n[red]Error running quest:[/red] {e}")
        raise
    except Exception as e:
        console.print(f"\n[red]Unexpected error:[/red] {e}")
        raise


def main():
    parser = argparse.ArgumentParser(
        description="Run Space Rangers quest interactively",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("quest_path", help="Path to the .qm file")
    parser.add_argument("--lang", choices=["rus", "eng"], default="rus",
                      help="Language for quest text (default: rus)")
    args = parser.parse_args()

    # Print title
    console.print(Panel(
        "[bold blue]Space Rangers Quest Player[/bold blue]\n"
        "[dim]Interactive text quest player for Space Rangers[/dim]",
        border_style="blue"
    ))
    console.print()

    play_quest(args.quest_path, args.lang)


if __name__ == "__main__":
    main()
