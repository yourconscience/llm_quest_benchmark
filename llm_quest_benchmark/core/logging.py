"""Unified logging module for LLM Quest Benchmark"""
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
import os

from rich.logging import RichHandler
from llm_quest_benchmark.dataclasses.logging import QuestStep


class LogManager:
    """Centralized logging configuration"""
    def __init__(self, name: str = "llm-quest"):
        # Set up logging with rich handler for console output only if not already configured
        if not logging.getLogger().handlers:
            logging.basicConfig(
                level="INFO",
                format="%(message)s",
                datefmt="[%X]",
                handlers=[RichHandler(rich_tracebacks=True)]
            )
        self.log = logging.getLogger(name)

        # Set transformers logging level
        os.environ["TRANSFORMERS_VERBOSITY"] = "error"

    def setup(self, debug: bool = False) -> None:
        """Configure logging based on debug mode"""
        self.log.setLevel(logging.DEBUG if debug else logging.INFO)
        if debug:
            self.log.debug("Debug logging enabled")

    def get_logger(self):
        """Get the configured logger"""
        return self.log


class QuestLogger:
    """Unified logger for quest execution and metrics"""
    def __init__(self,
                 name: str = "quest",
                 debug: bool = False,
                 agent: str = None):
        self.logger = logging.getLogger(name)
        self.debug = debug
        self.agent = agent
        self.steps: List[QuestStep] = []
        self.quest_file: Optional[str] = None

        # Always set up metrics file
        metrics_dir = Path("metrics")
        metrics_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.metrics_file = metrics_dir / f"quest_run_{timestamp}.jsonl"

        # Configure console output if not already configured
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter('%(message)s')
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)

        self.logger.setLevel(logging.DEBUG if debug else logging.INFO)

    def set_quest_file(self, quest_file: str) -> None:
        """Set the quest file being run"""
        self.quest_file = quest_file
        if self.debug:
            self.logger.debug(f"Running quest: {quest_file}")

    def log_step(self,
                 step: int,
                 state: str,
                 choices: list,
                 response: str,
                 reward: float = 0.0,
                 metrics: Dict[str, Any] = None,
                 llm_response: Optional[Dict[str, Any]] = None) -> None:
        """Log a quest step with metrics"""
        quest_step = QuestStep(
            step=step,
            state=state,
            choices=choices,
            response=response,
            reward=reward,
            metrics=metrics,
            llm_response=llm_response
        )
        self.steps.append(quest_step)
        # Log into console if debug is enabled
        # self.logger.debug(quest_step.to_console_line())

        # Add quest metadata to first step
        step_data = quest_step.to_json()
        if step == 1:
            step_data.update({
                "quest_file": self.quest_file,
                "agent": self.agent,
                "debug": self.debug
            })

        # Always save metrics in JSONL format with UTF-8 encoding
        with open(self.metrics_file, "a", encoding='utf-8') as f:
            f.write(json.dumps(step_data, ensure_ascii=False) + "\n")

        # Debug logging if enabled
        # if self.debug:
        #     self.logger.debug(f"Step {step} details:")
        #     self.logger.debug(f"State: {state[:200]}...")
        #     self.logger.debug(f"Response: {response}")
        #     if metrics:
        #         self.logger.debug(f"Metrics: {json.dumps(metrics, indent=2, ensure_ascii=False)}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get aggregated metrics for the quest run"""
        return {
            "quest_file": self.quest_file,
            "agent": self.agent,
            "total_steps": len(self.steps),
            "total_reward": sum(step.reward for step in self.steps),
            "steps": [step.to_json() for step in self.steps],
        }

    def get_log_entries(self) -> List[Dict[str, Any]]:
        """Get all log entries for the quest run"""
        return [step.to_json() for step in self.steps]