import argparse
import subprocess
import json
from pathlib import Path
from typing import Generator, Dict, Any

class QuestInterruptedException(Exception):
    """Raised when quest execution is interrupted"""

class QMInteractiveRunner:
    def __init__(self, qm_path: str):
        self.qm_path = Path(qm_path)
        self.process = None
        self._validate_environment()

    def _validate_environment(self):
        ts_path = Path("space-rangers-quest")
        if not (ts_path / "src/lib/qmreader.ts").exists():
            raise FileNotFoundError("Space Rangers submodule not initialized")

    def __enter__(self) -> Generator[Dict[str, Any], int, None]:
        cmd = [
            "npx", "ts-node",
            str(Path("scripts/consoleplayer.ts").resolve()),
            str(self.qm_path.resolve())
        ]

        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line-buffered
            universal_newlines=True
        )
        return self._communicate()

    def _communicate(self):
        try:
            while True:
                output = self.process.stdout.readline()
                if not output and self.process.poll() is not None:
                    break

                if output:
                    try:
                        state = json.loads(output)
                        choice = yield state
                        self._send_choice(choice)
                    except json.JSONDecodeError:
                        if "Debug" in output:  # Ignore TS debug messages
                            continue
                        raise RuntimeError(f"Invalid TS output: {output}")

        finally:
            self._cleanup()

    def _send_choice(self, choice: int):
        self.process.stdin.write(f"{choice}\n")
        self.process.stdin.flush()

    def _cleanup(self):
        if self.process.poll() is None:
            self.process.terminate()
        self.process = None

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cleanup()

def console_interface(quest_path: str):
    with QMInteractiveRunner(quest_path) as quest:
        try:
            state = next(quest)
            while True:
                print(f"\nDay {state['daysPassed']}")
                print(state["text"])
                print("\nChoices:")
                for choice in state["choices"]:
                    print(f"{choice['id']}: {choice['text']}")

                try:
                    choice = int(input("\nYour choice: "))
                    state = quest.send(choice)
                except ValueError:
                    print("Please enter a valid number")

        except StopIteration:
            print("Quest completed!")
        except QuestInterruptedException:
            print("\nQuest interrupted")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Space Rangers quest interactively in console")
    parser.add_argument("quest_path", type=str, help="Path to the quest file",
                        default="quests/Boat.qm")
    args = parser.parse_args()
    console_interface(args.quest_path)