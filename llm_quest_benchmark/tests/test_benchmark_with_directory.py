"""Test running a benchmark with the directory path"""
import logging
import yaml
import json
from pathlib import Path
import sys

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the project root to Python path to ensure imports work
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from llm_quest_benchmark.executors.benchmark import run_benchmark
from llm_quest_benchmark.schemas.config import BenchmarkConfig, AgentConfig


def create_test_config():
    """Create a test benchmark configuration with directory path"""
    return {
        "name": "Directory Benchmark Test",
        "quests": ["quests/kr2_en"],  # Use a directory path
        "agents": [{
            "model": "random_choice",
            "skip_single": True,
            "temperature": 0.7
        }],
        "quest_timeout": 10,  # Short timeout for testing
        "debug": True,
        "output_dir": "metrics/test_dir_benchmark"
    }


def test_benchmark_with_directory():
    """Test running a benchmark with a directory path"""
    # Create and validate config
    config_dict = create_test_config()
    logger.info(f"Created test config: {json.dumps(config_dict, indent=2)}")

    try:
        # Convert agent dictionaries to AgentConfig objects first
        agent_configs = []
        for agent_dict in config_dict["agents"]:
            agent_configs.append(AgentConfig(**agent_dict))

        # Then create the benchmark config with the agent objects
        config_dict["agents"] = agent_configs
        config = BenchmarkConfig(**config_dict)
        logger.info("Config validation passed")

        # Run benchmark with properly initialized config
        logger.info("Running benchmark with directory path...")
        results = run_benchmark(config)

        # Calculate success rate
        successes = len([r for r in results if r.get('outcome') == 'SUCCESS'])
        success_rate = successes / len(results) if results else 0

        logger.info(f"Benchmark completed with {len(results)} quests")
        logger.info(f"Success rate: {success_rate:.2f} ({successes}/{len(results)})")

    except Exception as e:
        logger.error(f"Error running benchmark: {e}", exc_info=True)
        return False

    return True


if __name__ == "__main__":
    if test_benchmark_with_directory():
        logger.info("Directory benchmark test passed!")
    else:
        logger.error("Directory benchmark test failed!")
        sys.exit(1)
