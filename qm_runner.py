import subprocess
import argparse
from pathlib import Path

def run_quest(quest_path: str):
    """Run quest in interactive mode using TypeScript console player"""
    ts_path = Path("space-rangers-quest")
    if not ts_path.exists():
        raise FileNotFoundError("Space Rangers submodule not found")

    cmd = [
        "npx", "ts-node",
        str(Path("scripts/consoleplayer.ts").resolve()),
        str(Path(quest_path).resolve())
    ]

    # Run TypeScript process and connect it directly to terminal
    process = subprocess.Popen(
        cmd,
        cwd=".",  # Run from our project root, not from submodule
    )

    try:
        process.wait()
    except KeyboardInterrupt:
        process.terminate()
        print("\nQuest aborted by user")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Space Rangers quest interactively")
    parser.add_argument("quest_path", help="Path to the .qm file")
    args = parser.parse_args()

    run_quest(args.quest_path)