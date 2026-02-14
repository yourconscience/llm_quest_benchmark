"""Configuration dataclasses for benchmark runs"""
import os
import yaml
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from pathlib import Path

from llm_quest_benchmark.constants import (
    DEFAULT_MODEL,
    DEFAULT_TEMPLATE,
    DEFAULT_TEMPERATURE,
    MODEL_CHOICES,
    SYSTEM_ROLE_TEMPLATE
)

# Default benchmark configuration
DEFAULT_BENCHMARK_CONFIG = {
    "quests": ["quests/Boat.qm"],
    "agents": [
        {
            "model": "random_choice",
            "skip_single": True,
            "temperature": 0.0,
            "template": "reasoning.jinja"
        },
        {
            "model": "gpt-5-mini",
            "skip_single": True,
            "temperature": 0.4,
            "template": "reasoning.jinja"
        }
    ],
    "debug": False,
    "quest_timeout": 30,
    "output_dir": "results/benchmarks",
    "name": "Default Benchmark"
}

def get_default_benchmark_yaml() -> str:
    """Get the default benchmark configuration from default.yaml file"""
    import os
    from pathlib import Path
    
    # Find the project root (where configs directory is)
    project_root = Path(__file__).parent.parent.parent
    config_path = project_root / "configs" / "default.yaml"
    
    # Fallback to a basic config if file doesn't exist
    if not config_path.exists():
        return """# Example benchmark configuration
quests:
  - quests/Boat.qm
agents:
  - model: random_choice
  - model: gpt-5-mini
    template: reasoning.jinja
debug: true
# One worker per agent will be used automatically
output_dir: results/benchmarks"""
    
    # Read the file content
    with open(config_path, 'r') as f:
        return f.read()


@dataclass
class AgentConfig:
    """Configuration for a single agent in benchmark"""
    model: str = DEFAULT_MODEL
    system_template: str = SYSTEM_ROLE_TEMPLATE
    action_template: str = DEFAULT_TEMPLATE
    temperature: float = DEFAULT_TEMPERATURE
    skip_single: bool = False
    debug: bool = False
    benchmark_id: Optional[str] = None  # Added to link runs to benchmarks

    def __post_init__(self):
        if self.model not in ("random_choice", "human"):
            # Keep parser compatibility for legacy names while UI remains clean.
            from llm_quest_benchmark.llm.client import is_supported_model_name

            if not is_supported_model_name(self.model):
                raise ValueError(f"Invalid model: {self.model}. Supported models: {MODEL_CHOICES}")
        if not (0.0 <= self.temperature <= 2.0):
            raise ValueError(f"Temperature must be between 0.0 and 2.0, got {self.temperature}")

    @property
    def agent_id(self) -> str:
        """Generate a unique agent ID based on configuration values"""
        import hashlib
        # Create a string with the key configuration values
        config_str = f"{self.model}_{self.temperature}_{self.system_template}_{self.action_template}"
        # Generate a short hash (first 8 characters)
        hash_val = hashlib.md5(config_str.encode()).hexdigest()[:8]
        # Include model and temperature in the ID for better readability
        return f"{self.model}_t{self.temperature}_{hash_val}"


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark run"""
    quests: List[str]  # List of quest files or directories
    agents: List[AgentConfig]  # List of agent configurations to test
    debug: bool = False
    quest_timeout: int = 60  # Timeout per quest
    benchmark_timeout: Optional[int] = None  # Total timeout for all quests, defaults to quest_timeout * num_quests
    output_dir: Optional[str] = "results/benchmarks"
    name: Optional[str] = "baseline"  # Name of the benchmark run
    renderer: str = "progress"  # Type of renderer to use (progress, simple, etc.)
    benchmark_id: Optional[str] = None  # Unique ID for the benchmark run
    max_quests: Optional[int] = None  # Maximum number of quests to run (useful for testing)
    max_workers: Optional[int] = None  # Optional parallel workers for future benchmark scheduling

    def __post_init__(self):
        # Validate quest paths
        for quest_path in self.quests:
            # Skip validation for glob patterns
            if '*' in quest_path:
                continue
                
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
            agents = []
            for agent in data['agents']:
                # Handle 'template' key which maps to action_template in AgentConfig
                if 'template' in agent:
                    agent['action_template'] = agent.pop('template')
                agents.append(AgentConfig(**agent))
            data['agents'] = agents

        return cls(**data)
