"""Unified logging module for LLM Quest Benchmark"""
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import os

from rich.logging import RichHandler


class LogManager:
    """Centralized logging configuration"""
    def __init__(self, name: str = "llm-quest"):
        # Set up logging with rich handler for console output
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
            # Create logs directory if it doesn't exist
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)

            # Add file handler for debug logging
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            debug_handler = logging.FileHandler(log_dir / f"llm_quest_{timestamp}.log")
            debug_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            debug_handler.setFormatter(formatter)
            self.log.addHandler(debug_handler)
            self.log.debug("Debug logging enabled")

    def get_logger(self):
        """Get the configured logger"""
        return self.log


@dataclass
class QuestStep:
    """Single step in quest execution"""
    step: int
    state: str
    choices: list
    prompt: str
    response: str
    reward: float = 0.0
    metrics: Dict[str, Any] = None
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_console_line(self, is_llm: bool = False) -> str:
        """Format step for console output based on player type"""
        if is_llm:
            return f"Step {self.step} | Action: {self.response} | Reward: {self.reward} | Choices: {len(self.choices)}"
        else:
            # For human players, just show the state and choices
            return f"Step {self.step} | Choices: {len(self.choices)}"

    def to_json(self) -> Dict[str, Any]:
        """Convert step to JSON format for analysis"""
        return {
            "step": self.step,
            "timestamp": self.timestamp,
            "state": self.state,
            "choices": self.choices,
            "prompt": self.prompt,
            "response": self.response,
            "reward": self.reward,
            "metrics": self.metrics or {}
        }


class QuestLogger:
    """Unified logger for quest execution and metrics"""
    def __init__(self,
                 name: str = "quest",
                 debug: bool = False,
                 is_llm: bool = False,
                 model: str = None,
                 template: str = None):
        # Set up logging
        self.logger = logging.getLogger(name)
        self.debug = debug
        self.is_llm = is_llm
        self.model = model
        self.template = template
        self.steps: List[QuestStep] = []
        self.quest_file: Optional[str] = None

        # Always set up metrics file
        metrics_dir = Path("metrics")
        metrics_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.metrics_file = metrics_dir / f"quest_run_{timestamp}.jsonl"

        # Configure console output
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
                 prompt: str,
                 response: str,
                 reward: float = 0.0,
                 metrics: Dict[str, Any] = None) -> None:
        """Log a quest step with metrics"""
        quest_step = QuestStep(
            step=step,
            state=state,
            choices=choices,
            prompt=prompt,
            response=response,
            reward=reward,
            metrics=metrics
        )
        self.steps.append(quest_step)

        # Console output based on player type
        self.logger.info(quest_step.to_console_line(is_llm=self.is_llm))

        # Add quest metadata to first step
        step_data = quest_step.to_json()
        if step == 1:
            step_data.update({
                "quest_file": self.quest_file,
                "is_llm": self.is_llm,
                "model": self.model,
                "template": self.template,
                "debug": self.debug
            })

        # Always save metrics in JSONL format with UTF-8 encoding
        with open(self.metrics_file, "a", encoding='utf-8') as f:
            f.write(json.dumps(step_data, ensure_ascii=False) + "\n")

        # Debug logging if enabled
        if self.debug:
            self.logger.debug(f"Step {step} details:")
            self.logger.debug(f"State: {state[:200]}...")
            self.logger.debug(f"Prompt: {prompt[:200]}...")
            self.logger.debug(f"Response: {response}")
            self.logger.debug(f"Reward: {reward}")
            if metrics:
                self.logger.debug(f"Metrics: {json.dumps(metrics, indent=2, ensure_ascii=False)}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get aggregated metrics for the quest run"""
        return {
            "quest_file": self.quest_file,
            "total_steps": len(self.steps),
            "total_reward": sum(step.reward for step in self.steps),
            "steps": [step.to_json() for step in self.steps],
            "is_llm": self.is_llm,
            "model": self.model,
            "template": self.template,
            "debug": self.debug
        }