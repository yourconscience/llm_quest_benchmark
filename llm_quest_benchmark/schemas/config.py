"""Configuration dataclasses for benchmark runs"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from llm_quest_benchmark.constants import (
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    MODEL_CHOICES,
    SYSTEM_ROLE_TEMPLATE,
    normalize_template_name,
)

# Default benchmark configuration
DEFAULT_BENCHMARK_CONFIG = {
    "quests": ["quests/Boat.qm"],
    "agents": [
        {"model": "random_choice", "skip_single": True, "temperature": 0.0, "harness": "random_choice"},
        {"model": "gpt-5-mini", "skip_single": True, "temperature": 0.4, "harness": "reasoning_recent"},
    ],
    "debug": False,
    "quest_timeout": 30,
    "output_dir": "results/benchmarks",
    "name": "Default Benchmark",
}


def get_default_benchmark_yaml() -> str:
    """Get the default benchmark configuration from default.yaml file"""
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
    harness: random_choice
  - model: gpt-5-mini
    harness: reasoning_recent
debug: true
# One worker per agent will be used automatically
output_dir: results/benchmarks"""

    # Read the file content
    with open(config_path) as f:
        return f.read()


@dataclass
class HarnessConfig:
    """Configuration for a single harness in benchmark"""

    model: str = DEFAULT_MODEL
    system_template: str = SYSTEM_ROLE_TEMPLATE
    harness: str = "reasoning_recent"
    temperature: float = DEFAULT_TEMPERATURE
    runs: int = 1
    skip_single: bool = False
    debug: bool = False
    benchmark_id: str | None = None
    compaction_interval: int = 50
    restore_limit: int | None = None
    adaptive_stall_steps: int | None = None

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        system_template: str = SYSTEM_ROLE_TEMPLATE,
        harness: str = "reasoning_recent",
        temperature: float = DEFAULT_TEMPERATURE,
        runs: int = 1,
        skip_single: bool = False,
        debug: bool = False,
        benchmark_id: str | None = None,
        compaction_interval: int = 50,
        restore_limit: int | None = None,
        adaptive_stall_steps: int | None = None,
        **unexpected_keys,
    ):
        if unexpected_keys:
            unexpected = ", ".join(sorted(unexpected_keys))
            raise TypeError(f"Unexpected HarnessConfig key(s): {unexpected}")

        self.model = model
        self.system_template = system_template
        self.harness = harness
        self.temperature = temperature
        self.runs = runs
        self.skip_single = skip_single
        self.debug = debug
        self.benchmark_id = benchmark_id
        self.compaction_interval = compaction_interval
        self.restore_limit = restore_limit
        self.adaptive_stall_steps = adaptive_stall_steps
        self.__post_init__()

    def __post_init__(self):
        self.system_template = normalize_template_name(self.system_template)
        from llm_quest_benchmark.harnesses.specs import (
            HARNESS_SPECS,
            is_random_choice_harness,
            valid_harness_names,
            validate_exclusive_knobs,
        )

        if self.harness not in HARNESS_SPECS and not is_random_choice_harness(self.harness):
            raise ValueError(f"Invalid harness: {self.harness}. Supported harnesses: {valid_harness_names()}")
        if self.harness == "human" and self.model != "human":
            raise ValueError("Use model: human with harness: human")
        if self.model == "human" and self.harness != "human":
            raise ValueError("Use harness: human with model: human")
        if is_random_choice_harness(self.harness) and self.model != "random_choice":
            raise ValueError("Use model: random_choice with random_choice harnesses")
        if is_random_choice_harness(self.model) and not is_random_choice_harness(self.harness):
            raise ValueError("Use harness: random_choice with model: random_choice")
        if self.model not in ("human",) and not is_random_choice_harness(self.model):
            from llm_quest_benchmark.llm.client import is_supported_model_name

            if not is_supported_model_name(self.model):
                raise ValueError(f"Invalid model: {self.model}. Supported models: {MODEL_CHOICES}")
        if not (0.0 <= self.temperature <= 2.0):
            raise ValueError(f"Temperature must be between 0.0 and 2.0, got {self.temperature}")
        if self.runs < 1:
            raise ValueError(f"runs must be >= 1, got {self.runs}")
        if self.compaction_interval < 1:
            raise ValueError(f"compaction_interval must be >= 1, got {self.compaction_interval}")

        validate_exclusive_knobs(self.harness, self.knob_values())
        if self.restore_limit is not None and self.restore_limit < 1:
            raise ValueError(f"restore_limit must be >= 1, got {self.restore_limit}")
        if self.adaptive_stall_steps is not None and self.adaptive_stall_steps < 1:
            raise ValueError(f"adaptive_stall_steps must be >= 1, got {self.adaptive_stall_steps}")

    def knob_values(self) -> dict[str, int | None]:
        """Material knob values considered by the harness specification."""
        return {
            "compaction_interval": self.compaction_interval,
            "restore_limit": self.restore_limit,
            "adaptive_stall_steps": self.adaptive_stall_steps,
        }

    def treatment(self):
        """Canonical treatment for this configuration."""
        from llm_quest_benchmark.harnesses.specs import build_treatment

        return build_treatment(
            harness=self.harness,
            model=self.model,
            temperature=self.temperature,
            system_template=self.system_template,
            knob_values=self.knob_values(),
        )

    @property
    def harness_id(self) -> str:
        """Stable harness ID derived from the canonical treatment signature."""
        signature = self.treatment().signature
        return f"{self.model}_t{self.temperature}_{self.harness}_{signature.split('_', 1)[1][:8]}"

    @property
    def agent_id(self) -> str:
        """Run identity used for the results directory and DB rows."""
        return self.harness_id


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark run"""

    quests: list[str]  # List of quest files or directories
    agents: list[HarnessConfig]  # List of harness configurations to test
    debug: bool = False
    quest_timeout: int = 60  # Timeout per quest
    benchmark_timeout: int | None = None  # Total timeout for all quests, defaults to quest_timeout * num_quests
    max_steps: int | None = None  # Shared cap on agent steps per quest; None preserves unbounded behavior
    output_dir: str | None = "results/benchmarks"
    name: str | None = "baseline"  # Name of the benchmark run
    renderer: str = "progress"  # Type of renderer to use (progress, simple, etc.)
    benchmark_id: str | None = None  # Unique ID for the benchmark run
    max_quests: int | None = None  # Maximum number of quests to run (useful for testing)
    max_workers: int | None = None  # Optional parallel workers for future benchmark scheduling
    progress_manifest: str | None = None  # Optional curated milestone manifest (YAML)

    def __post_init__(self):
        # Validate quest paths
        for quest_path in self.quests:
            # Skip validation for glob patterns
            if "*" in quest_path:
                continue

            path = Path(quest_path)
            if not path.exists():
                raise ValueError(f"Quest path does not exist: {quest_path}")
            if not (path.is_file() and path.suffix == ".qm") and not path.is_dir():
                raise ValueError(f"Quest path must be a .qm file or directory: {quest_path}")

        if self.max_steps is not None and self.max_steps < 1:
            raise ValueError(f"max_steps must be >= 1, got {self.max_steps}")

        if self.progress_manifest:
            # Fail fast on an invalid manifest rather than mid-benchmark.
            from llm_quest_benchmark.core.progress import ProgressManifest

            ProgressManifest.from_file(self.progress_manifest)

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "BenchmarkConfig":
        """Create config from YAML file"""
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # Convert agent configs
        if "agents" in data:
            data["agents"] = [HarnessConfig(**agent) for agent in data["agents"]]

        return cls(**data)
