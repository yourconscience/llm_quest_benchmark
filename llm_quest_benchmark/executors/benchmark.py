"""Benchmark executor for running multiple quests with multiple agents"""
import glob
import json
import logging
import os
import queue
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from llm_quest_benchmark.agents.agent_factory import create_agent
from llm_quest_benchmark.agents.llm_agent import LLMAgent
from llm_quest_benchmark.constants import DEFAULT_QUEST_TIMEOUT
from llm_quest_benchmark.core.logging import LogManager, QuestLogger
from llm_quest_benchmark.core.runner import run_quest_with_timeout
from llm_quest_benchmark.core.time import DEFAULT_QUEST_TIMEOUT, calculate_benchmark_timeout
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.renderers.factory import create_renderer
from llm_quest_benchmark.renderers.progress import ProgressRenderer
from llm_quest_benchmark.schemas.config import AgentConfig, BenchmarkConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True  # Override any existing logging configuration
)

# Reduce verbosity of other loggers
logging.getLogger('quest').setLevel(logging.WARNING)
logging.getLogger('llm_quest_benchmark').setLevel(logging.WARNING)
logging.getLogger('llm_quest_benchmark.executors.ts_bridge').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def get_quest_files(quest_paths: List[str], max_quests: Optional[int] = None) -> List[Path]:
    """Get list of quest files from paths (files or directories or glob patterns)

    Args:
        quest_paths (List[str]): List of quest files, directories, or glob patterns
        max_quests (Optional[int]): Maximum number of quests to return

    Returns:
        List[Path]: List of quest file paths
    """
    from llm_quest_benchmark.core.quest_registry import resolve_quest_paths
    quest_files = resolve_quest_paths(quest_paths)

    # Limit to max_quests if specified
    if max_quests is not None and max_quests > 0:
        quest_files = quest_files[:max_quests]
        logger.info(f"Limiting to {len(quest_files)} quests due to max_quests setting")

    return quest_files


def agent_worker(agent_config: AgentConfig,
                 quest_queue: queue.Queue,
                 results: List[Dict[str, Any]],
                 results_lock: threading.Lock,
                 benchmark_id: str,
                 quest_timeout: int,
                 progress_callback=None) -> None:
    """Worker function to process quests for a specific agent

    Args:
        agent_config: Configuration for the agent
        quest_queue: Queue of quests to process
        results: Shared list to store results
        results_lock: Lock for thread-safe access to results
        benchmark_id: ID for the benchmark run
        quest_timeout: Timeout for each quest
        progress_callback: Optional callback to report progress
    """
    # Set benchmark_id in agent_config for database tracking
    agent_config.benchmark_id = benchmark_id

    # Create agent
    agent = create_agent(model=agent_config.model,
                         temperature=agent_config.temperature,
                         system_template=agent_config.system_template,
                         action_template=agent_config.action_template,
                         skip_single=agent_config.skip_single,
                         debug=agent_config.debug)

    # Get agent_id from agent_config
    agent_id = agent_config.agent_id

    # Process quests from the queue
    while True:
        try:
            # Get a quest from the queue (non-blocking)
            quest_file = quest_queue.get_nowait()
        except queue.Empty:
            # No more quests in the queue
            break

        # Always convert Path to string for consistent handling
        quest_str = str(quest_file)
        quest_name = Path(quest_file).name

        logger.info(f"Agent {agent_id} running quest {quest_name}")

        try:
            # Run quest with timeout - always use string not Path
            outcome = run_quest_with_timeout(quest_str,
                                             agent,
                                             timeout=quest_timeout,
                                             agent_config=agent_config)

            # Call progress callback if provided
            if progress_callback:
                # Always pass string paths to callback
                progress_callback(quest_str, agent_id)

            # Create result entry
            result = {
                'quest': quest_str,
                'model': agent_config.model,
                'temperature': agent_config.temperature,
                'template': agent_config.action_template,
                'agent_id': agent_id,
                'outcome': outcome.name if outcome else QuestOutcome.ERROR.name,
                'reward': getattr(outcome, 'reward', 0.0),
                'error': None
            }

        except Exception as e:
            # Log the error but continue with other quests
            logger.error(f"Error running quest {quest_file} with agent {agent_id}: {e}")

            # Create error result
            result = {
                'quest': str(quest_file),
                'model': agent_config.model,
                'temperature': agent_config.temperature,
                'template': agent_config.action_template,
                'agent_id': agent_id,
                'outcome': QuestOutcome.ERROR.name,
                'reward': 0.0,
                'error': str(e)
            }

        # Add result to the shared results list (thread-safe)
        with results_lock:
            results.append(result)

        # Mark this quest as done in the queue
        quest_queue.task_done()


def run_benchmark(config: BenchmarkConfig, progress_callback=None) -> List[Dict[str, Any]]:
    """Run benchmark on a set of quests with multiple agents

    Uses a worker per agent design where each agent processes quests from a shared queue.
    This ensures that each agent only works on one quest at a time.

    Args:
        config: Benchmark configuration
        progress_callback: Optional callback to report progress

    Returns:
        List of results for each quest/agent combination
    """
    # Generate a benchmark ID if not provided
    if not config.benchmark_id:
        config.benchmark_id = f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Create logger for benchmark
    logger_manager = QuestLogger(debug=config.debug)
    logger.info(f"Running benchmark with ID: {config.benchmark_id}")

    # Expand quest paths into actual quest files
    quest_files = get_quest_files(config.quests, config.max_quests)
    logger.info(f"Found {len(quest_files)} quests to run")

    # Print summary of what will be run
    logger.info(f"Running {len(quest_files)} quests with {len(config.agents)} agents")
    logger.info(f"Agents: {', '.join(a.agent_id for a in config.agents)}")

    # Shared results list and lock
    results = []
    results_lock = threading.Lock()

    # Queue no longer used with sequential processing

    # Ensure each agent processes all quests
    for agent_config in config.agents:
        # Process quests directly for this agent (simpler than threads)
        for quest_file in quest_files:
            quest_str = str(quest_file)
            quest_name = Path(quest_file).name

            logger.info(f"Agent {agent_config.agent_id} running quest {quest_name}")

            try:
                # Set the benchmark_id in agent_config for database tracking
                agent_config.benchmark_id = config.benchmark_id

                # Create agent
                agent = create_agent(model=agent_config.model,
                                     temperature=agent_config.temperature,
                                     system_template=agent_config.system_template,
                                     action_template=agent_config.action_template,
                                     skip_single=agent_config.skip_single,
                                     debug=agent_config.debug)

                # Run quest with timeout
                outcome = run_quest_with_timeout(quest_str,
                                                 agent,
                                                 timeout=config.quest_timeout,
                                                 agent_config=agent_config)

                # Call progress callback if provided
                if progress_callback:
                    progress_callback(quest_str, agent_config.agent_id)

                # Create result entry
                result = {
                    'quest': quest_str,
                    'model': agent_config.model,
                    'temperature': agent_config.temperature,
                    'template': agent_config.action_template,
                    'agent_id': agent_config.agent_id,
                    'outcome': outcome.name if outcome else QuestOutcome.ERROR.name,
                    'reward': getattr(outcome, 'reward', 0.0),
                    'error': None
                }

            except Exception as e:
                # Log the error but continue with other quests
                logger.error(
                    f"Error running quest {quest_file} with agent {agent_config.agent_id}: {e}")

                # Create error result
                result = {
                    'quest': quest_str,
                    'model': agent_config.model,
                    'temperature': agent_config.temperature,
                    'template': agent_config.action_template,
                    'agent_id': agent_config.agent_id,
                    'outcome': QuestOutcome.ERROR.name,
                    'reward': 0.0,
                    'error': str(e)
                }

            # Add result to the shared results list
            with results_lock:
                results.append(result)

    # Prepare benchmark metrics
    benchmark_metrics = {
        'name': config.name,
        'benchmark_id': config.benchmark_id,
        'timestamp': datetime.now().isoformat(),
        'quests': [],
        'agents': [agent.agent_id for agent in config.agents],
        'results': results
    }

    # Organize results by quest
    quest_data = {}
    for result in results:
        quest = result['quest']
        if quest not in quest_data:
            quest_data[quest] = {'quest': quest, 'runs': []}
        quest_data[quest]['runs'].append(result)

    # Add organized quest data to benchmark metrics
    benchmark_metrics['quests'] = list(quest_data.values())

    # Save results if output dir specified
    if config.output_dir:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        metrics_root = Path(config.output_dir)
        metrics_root.mkdir(exist_ok=True, parents=True)

        # Save benchmark summary
        summary_file = metrics_root / f"benchmark_{timestamp}.json"
        with open(summary_file, 'w') as f:
            json.dump(benchmark_metrics, f, indent=2)

        logger.info(f"Benchmark results saved to {summary_file}")

    return results


def calculate_summary_stats(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate detailed summary statistics for benchmark results

    Args:
        results (List[Dict[str, Any]]): List of benchmark results

    Returns:
        Dict[str, Any]: Summary statistics
    """
    summary = {
        'models': {},
        'total_runs': len(results),
        'total_success': len([r for r in results if r['outcome'] == QuestOutcome.SUCCESS.name]),
        'total_failures': len([r for r in results if r['outcome'] == QuestOutcome.FAILURE.name]),
        'total_errors': len([r for r in results if r['outcome'] == QuestOutcome.ERROR.name]),
        'total_timeouts': len([r for r in results if r['outcome'] == QuestOutcome.TIMEOUT.name]),
        'success_rate': 0,
        'error_rate': 0,
        'failure_rate': 0,
        'timeout_rate': 0
    }

    # Calculate per-model statistics
    models = {r['model'] for r in results}
    for model in sorted(models):
        model_results = [r for r in results if r['model'] == model]
        success = len([r for r in model_results if r['outcome'] == QuestOutcome.SUCCESS.name])
        failed = len([r for r in model_results if r['outcome'] == QuestOutcome.FAILURE.name])
        error = len([r for r in model_results if r['outcome'] == QuestOutcome.ERROR.name])
        timeout = len([r for r in model_results if r['outcome'] == QuestOutcome.TIMEOUT.name])
        total = len(model_results)

        summary['models'][model] = {
            'total_runs': total,
            'success': success,
            'success_rate': success / total if total > 0 else 0,
            'failed': failed,
            'failure_rate': failed / total if total > 0 else 0,
            'errors': error,
            'error_rate': error / total if total > 0 else 0,
            'timeouts': timeout,
            'timeout_rate': timeout / total if total > 0 else 0
        }

    # Calculate overall rates
    total = len(results)
    if total > 0:
        summary['success_rate'] = summary['total_success'] / total
        summary['failure_rate'] = summary['total_failures'] / total
        summary['error_rate'] = summary['total_errors'] / total
        summary['timeout_rate'] = summary['total_timeouts'] / total

    return summary


def print_summary(results: List[Dict[str, Any]]) -> None:
    """Print benchmark results summary

    Args:
        results (List[Dict[str, Any]]): List of benchmark results
    """
    print("\nResults Summary:")
    print("=" * 80)

    # Calculate total steps (if available)
    steps_info_available = any('steps' in r for r in results)

    if steps_info_available:
        total_steps = sum(len(r.get('steps', [])) for r in results)
        steps_by_model = {}

    # Group by model
    models = {r['model'] for r in results}
    for model in sorted(models):
        model_results = [r for r in results if r['model'] == model]
        success = len([r for r in model_results if r['outcome'] == QuestOutcome.SUCCESS.name])
        failed = len([r for r in model_results if r['outcome'] == QuestOutcome.FAILURE.name])
        error = len([r for r in model_results if r['outcome'] == QuestOutcome.ERROR.name])
        timeout = len([r for r in model_results if r['outcome'] == QuestOutcome.TIMEOUT.name])
        total = len(model_results)

        # Calculate steps for this model (if available)
        if steps_info_available:
            model_steps = sum(len(r.get('steps', [])) for r in model_results)
            avg_steps = model_steps / total if total > 0 else 0
            steps_by_model[model] = (model_steps, avg_steps)

        print(f"\nModel: {model}")
        print(f"Total quests: {total}")
        print(f"Success: {success} ({success/total*100:.1f}%)")
        print(f"Failed: {failed} ({failed/total*100:.1f}%)")
        print(f"Error: {error} ({error/total*100:.1f}%)")
        print(f"Timeout: {timeout} ({timeout/total*100:.1f}%)")

        if steps_info_available:
            print(f"Total steps: {model_steps}")
            print(f"Average steps per quest: {avg_steps:.1f}")

    # Print overall steps summary (if available)
    if steps_info_available:
        print("\nOverall Steps Summary:")
        print("=" * 80)
        print(f"Total steps across all models: {total_steps}")
        print(f"Average steps per quest: {total_steps/len(results):.1f}")

    # List errors if any
    errors = [r for r in results if r.get('error')]
    if errors:
        print("\nErrors encountered:")
        print("=" * 80)
        for r in errors:
            print(f"{r['quest']} - {r['model']}: Error - {r['error']}")
