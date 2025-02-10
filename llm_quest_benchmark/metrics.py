"""
Module for logging metrics and tracing state evolution during quest runs.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class MetricsLogger:
    def __init__(self, auto_save: bool = False):
        self.steps = []  # List to store step-by-step logs
        self.auto_save = auto_save
        self.run_time = datetime.now().isoformat()
        self.quest_file = None

    def set_quest_file(self, quest_file: str):
        self.quest_file = quest_file

    def log_step(self, step: int, state: dict, action: str, reward: float):
        """
        Log one step of the quest run.

        Args:
            step (int): The current step number.
            state (dict): The representation of the game state (e.g. text, choices).
            action (str): The action produced by the agent.
            reward (float): The reward obtained at this step.
        """
        entry = {
            "step": step,
            "timestamp": datetime.now().isoformat(),
            "state": state,
            "action": action,
            "reward": reward,
        }
        self.steps.append(entry)

    def save(self) -> Optional[str]:
        if not self.auto_save or not self.quest_file:
            return None

        metrics_dir = Path("metrics")
        metrics_dir.mkdir(exist_ok=True)

        # Generate filename: metrics/questname_YYYYMMDD_HHMMSS.json
        quest_stem = Path(self.quest_file).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{quest_stem}_{timestamp}.json"
        filepath = metrics_dir / filename

        data = {
            "quest": self.quest_file,
            "start_time": self.run_time,
            "end_time": datetime.now().isoformat(),
            "steps": self.steps,
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        return str(filepath)