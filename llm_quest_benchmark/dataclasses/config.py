"""Configuration dataclasses for benchmark runs"""
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path

from llm_quest_benchmark.constants import (
    DEFAULT_MODEL,
    DEFAULT_TEMPLATE,
    DEFAULT_TEMPERATURE,
    MODEL_CHOICES,
    SYSTEM_ROLE_TEMPLATE
)


@dataclass
class AgentConfig:
    """Configuration for a single agent in benchmark"""
    model: str = DEFAULT_MODEL
    system_template: str = SYSTEM_ROLE_TEMPLATE
    action_template: str = DEFAULT_TEMPLATE
    temperature: float = DEFAULT_TEMPERATURE
    skip_single: bool = False
    debug: bool = False

    def __post_init__(self):
        if self.model not in MODEL_CHOICES:
            raise ValueError(f"Invalid model: {self.model}. Supported models: {MODEL_CHOICES}")
        if not (0.0 <= self.temperature <= 2.0):
            raise ValueError(f"Temperature must be between 0.0 and 2.0, got {self.temperature}")


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark run"""
    quests: List[str]  # List of quest files or directories
    agents: List[AgentConfig]  # List of agent configurations to test
    debug: bool = False
    quest_timeout: int = 60  # Timeout per quest
    benchmark_timeout: Optional[int] = None  # Total timeout for all quests, defaults to quest_timeout * num_quests
    max_workers: int = 4
    output_dir: Optional[str] = "metrics/quests"
    name: Optional[str] = "baseline"  # Name of the benchmark run
    renderer: str = "progress"  # Type of renderer to use (progress, simple, etc.)

    def __post_init__(self):
        # Validate quest paths
        for quest_path in self.quests:
            path = Path(quest_path)
            if not path.exists():
                raise ValueError(f"Quest path does not exist: {quest_path}")
            if not (path.is_file() and path.suffix == '.qm') and not path.is_dir():
                raise ValueError(f"Quest path must be a .qm file or directory: {quest_path}")

    @classmethod
    def from_yaml(cls, yaml_path: str) -> 'BenchmarkConfig':
        """Create config from YAML file"""
        import yaml
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # Convert agent configs
        if 'agents' in data:
            data['agents'] = [AgentConfig(**agent) for agent in data['agents']]

        return cls(**data)