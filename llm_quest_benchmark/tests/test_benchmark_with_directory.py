"""Test running a benchmark with the directory path"""
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from llm_quest_benchmark.executors.benchmark import run_benchmark
from llm_quest_benchmark.schemas.config import BenchmarkConfig, AgentConfig


def create_test_config():
    """Create a test benchmark configuration with directory path"""
    return {
        "name": "Directory Benchmark Test",
        "quests": ["quests/spacerangers.gitlab.io/borrowed/qm/SR 2.1.2121 eng"],
        "agents": [
            {
                "model": "random_choice",
                "skip_single": True,
                "temperature": 0.7
            }
        ],
        "quest_timeout": 4,  # Keep runtime below pytest global timeout
        "max_quests": 1,
        "debug": True,
        "output_dir": "results/benchmarks"
    }


def test_benchmark_with_directory():
    """Test running a benchmark with a directory path"""
    # Create and validate config
    config_dict = create_test_config()
    logger.info(f"Created test config: {json.dumps(config_dict, indent=2)}")

    # Convert agent dictionaries to AgentConfig objects first
    config_dict["agents"] = [AgentConfig(**agent_dict) for agent_dict in config_dict["agents"]]
    config = BenchmarkConfig(**config_dict)
    logger.info("Config validation passed")

    # Run benchmark with properly initialized config
    logger.info("Running benchmark with directory path...")
    results = run_benchmark(config)

    assert results, "Expected at least one benchmark result"
    successes = len([r for r in results if r.get('outcome') == 'SUCCESS'])
    success_rate = successes / len(results)

    logger.info(f"Benchmark completed with {len(results)} quests")
    logger.info(f"Success rate: {success_rate:.2f} ({successes}/{len(results)})")


if __name__ == "__main__":
    test_benchmark_with_directory()
    logger.info("Directory benchmark test passed!")
