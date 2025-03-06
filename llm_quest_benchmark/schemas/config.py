"""Configuration dataclasses for benchmark runs"""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from llm_quest_benchmark.constants import (
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    DEFAULT_TEMPLATE,
    MODEL_CHOICES,
    SYSTEM_ROLE_TEMPLATE,
)

# Default benchmark configuration
DEFAULT_BENCHMARK_CONFIG = {
    "quests": ["quests/boat.qm"],
    "agents": ["gpt-4o-default", "claude-3-haiku-default"],
    "debug": False,
    "quest_timeout": 30,
    "output_dir": "metrics/web_benchmark",
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
  - quests/boat.qm
agents:
  - gpt-4o-default
  - claude-3-haiku-default
debug: true
# One worker per agent will be used automatically
output_dir: metrics/test"""

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
    agent_id: Optional[str] = None  # Added to store predefined agent ID

    def __post_init__(self):
        if self.model not in MODEL_CHOICES:
            raise ValueError(f"Invalid model: {self.model}. Supported models: {MODEL_CHOICES}")
        if not (0.0 <= self.temperature <= 2.0):
            raise ValueError(f"Temperature must be between 0.0 and 2.0, got {self.temperature}")

    @property
    def generated_agent_id(self) -> str:
        """Generate a unique agent ID based on configuration values"""
        import hashlib

        # If agent_id is already set (predefined agent), use it
        if self.agent_id:
            return self.agent_id

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
    agents: List[str]  # List of agent IDs to test
    debug: bool = False
    quest_timeout: int = 60  # Timeout per quest
    benchmark_timeout: Optional[
        int] = None  # Total timeout for all quests, defaults to quest_timeout * num_quests
    output_dir: Optional[str] = "metrics/quests"
    name: Optional[str] = "baseline"  # Name of the benchmark run
    renderer: str = "progress"  # Type of renderer to use (progress, simple, etc.)
    benchmark_id: Optional[str] = None  # Unique ID for the benchmark run
    max_quests: Optional[int] = None  # Maximum number of quests to run (useful for testing)
    max_workers: Optional[int] = None  # Maximum number of parallel workers

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

        # Validate agent IDs
        from llm_quest_benchmark.agents.agent_manager import AgentManager
        agent_manager = AgentManager()
        valid_agent_ids = set(agent_manager.list_agents())

        for agent_id in self.agents:
            if agent_id not in valid_agent_ids:
                raise ValueError(
                    f"Unknown agent ID: {agent_id}. Available agents: {', '.join(valid_agent_ids)}")

    @classmethod
    def from_yaml(cls, yaml_path: str) -> 'BenchmarkConfig':
        """Create config from YAML file"""
        import yaml
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # Ensure agents are a list of strings (agent IDs)
        if 'agents' in data:
            agent_list = data['agents']

            # If we have a list of dictionaries (old format), convert to agent IDs
            if isinstance(agent_list, list) and any(
                    isinstance(agent, dict) for agent in agent_list):
                # This is for backward compatibility - we'll create agents for the old format
                # But warn that this format is deprecated
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    "Using deprecated agent configuration format with inline definitions. "
                    "Please use agent IDs instead.")

                # Create agents in agent manager for each inline agent config
                from llm_quest_benchmark.agents.agent_manager import AgentManager
                agent_manager = AgentManager()

                new_agent_ids = []
                for agent_spec in agent_list:
                    if isinstance(agent_spec, dict):
                        # Handle 'template' key which maps to action_template in AgentConfig
                        if 'template' in agent_spec:
                            agent_spec['action_template'] = agent_spec.pop('template')

                        # If agent_id is specified, use that
                        if 'agent_id' in agent_spec:
                            agent_id = agent_spec['agent_id']
                            # Check if this agent exists
                            if agent_id in agent_manager.list_agents():
                                new_agent_ids.append(agent_id)
                            else:
                                raise ValueError(f"Unknown agent ID: {agent_id}")
                        else:
                            # Create a new agent from inline config
                            agent_config = AgentConfig(**agent_spec)
                            agent_id = agent_config.generated_agent_id
                            # Create temporary agent if it doesn't exist
                            if agent_id not in agent_manager.list_agents():
                                agent_config.agent_id = agent_id  # Set the ID explicitly
                                agent_manager.create_agent(agent_config)
                            new_agent_ids.append(agent_id)
                    else:
                        # It's already an agent ID
                        new_agent_ids.append(agent_spec)

                # Replace with list of agent IDs
                data['agents'] = new_agent_ids

        return cls(**data)
