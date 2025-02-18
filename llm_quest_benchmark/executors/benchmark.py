"""Benchmark module for evaluating quest agents"""
import os
import sys
import logging
import json
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from typing import List, Dict, Any, Optional, Tuple

from llm_quest_benchmark.core.runner import run_quest_with_timeout
from llm_quest_benchmark.agents.agent_factory import create_agent
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.executors.benchmark_config import BenchmarkConfig, AgentConfig
from llm_quest_benchmark.core.time import calculate_benchmark_timeout, DEFAULT_QUEST_TIMEOUT

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


def get_quest_files(quest_paths: List[str]) -> List[Path]:
    """Get list of quest files from paths (files or directories)

    Args:
        quest_paths (List[str]): List of quest files or directories

    Returns:
        List[Path]: List of quest file paths
    """
    quest_files = []
    for path in quest_paths:
        p = Path(path)
        if p.is_file() and p.suffix == '.qm':
            quest_files.append(p)
        elif p.is_dir():
            # Add all .qm files in directory (non-recursive)
            quest_files.extend(p.glob("*.qm"))
    return sorted(quest_files)  # Sort for consistent ordering


def run_benchmark(config: BenchmarkConfig) -> List[Dict[str, Any]]:
    """Run benchmark on a set of quests with multiple agents

    Args:
        config (BenchmarkConfig): Benchmark configuration

    Returns:
        List[Dict[str, Any]]: List of benchmark results
    """
    # Get all quest files
    quest_files = get_quest_files(config.quests)
    if not quest_files:
        logger.warning(f"No .qm files found in provided paths: {config.quests}")
        return []

    # Create agents first
    agents = []
    for agent_config in config.agents:
        try:
            agent = create_agent(agent_config.model)
            agents.append((agent, agent_config))
        except Exception as e:
            logger.error(f"Failed to create agent {agent_config.model}: {e}")
            continue

    # Prepare tasks - each quest with each agent
    all_tasks: List[Tuple[Path, Any, AgentConfig]] = [
        (quest, agent, agent_config)
        for quest in quest_files
        for agent, agent_config in agents
    ]

    # Calculate appropriate timeouts
    quest_timeout = min(config.timeout_seconds, DEFAULT_QUEST_TIMEOUT)  # Use shorter of configured or default
    benchmark_timeout = calculate_benchmark_timeout(
        num_quests=len(quest_files),
        num_agents=len(config.agents),
        num_workers=config.max_workers,
        quest_timeout=quest_timeout
    )

    # Run tasks in parallel
    results = []
    benchmark_metrics = {
        'timestamp': datetime.now().isoformat(),
        'config': {
            'quest_timeout': quest_timeout,
            'benchmark_timeout': benchmark_timeout,
            'debug': config.debug,
            'max_workers': config.max_workers,
        },
        'agents': [
            {
                'model': agent_config.model,
                'template': agent_config.template,
                'temperature': agent_config.temperature,
                'skip_single': agent_config.skip_single
            }
            for _, agent_config in agents
        ],
        'quests': [],
        'summary': {
            'total_quests': len(quest_files),
            'total_runs': len(all_tasks),
            'outcomes': {}
        }
    }

    with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
        # Submit all tasks
        future_to_task = {
            executor.submit(
                run_quest_with_timeout,
                str(quest),
                agent,
                timeout_seconds=quest_timeout,  # Use calculated quest timeout
                debug=config.debug,
                skip_single=agent_config.skip_single,
            ): (quest, agent, agent_config)
            for quest, agent, agent_config in all_tasks
        }

        # Wait for each future to complete with timeout
        for future in as_completed(future_to_task):
            quest, agent, agent_config = future_to_task[future]
            try:
                result = future.result(timeout=quest_timeout)  # Use same timeout for consistency
                # Add agent config info to result
                result['model'] = agent_config.model
                result['template'] = agent_config.template
                result['temperature'] = agent_config.temperature
                results.append(result)

                status = 'SUCCESS' if result['outcome'] == QuestOutcome.SUCCESS.name else 'FAILED'
                error_msg = f" (Error: {result['error']})" if result['error'] else ""
                logger.info(f"{result['quest']} - {agent_config.model}: {status}{error_msg}")

            except (TimeoutError, Exception) as e:
                error_msg = f"Timeout" if isinstance(e, TimeoutError) else f"{type(e).__name__}: {str(e)}"
                logger.error(f"Quest {quest.name} with agent {agent_config.model} failed: {error_msg}")

                # Add failed result
                result = {
                    'quest': quest.name,
                    'model': agent_config.model,
                    'template': agent_config.template,
                    'temperature': agent_config.temperature,
                    'outcome': QuestOutcome.TIMEOUT.name if isinstance(e, TimeoutError) else QuestOutcome.ERROR.name,
                    'error': error_msg,
                    'timestamp': datetime.now().isoformat(),
                    'steps': []
                }
                results.append(result)

            # Update benchmark metrics with outcomes
            outcome = result['outcome']
            if outcome not in benchmark_metrics['summary']['outcomes']:
                benchmark_metrics['summary']['outcomes'][outcome] = 0
            benchmark_metrics['summary']['outcomes'][outcome] += 1

    # Save results if output directory specified
    if config.output_dir:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save detailed quest metrics
        quests_dir = os.path.join(config.output_dir, "quests")
        os.makedirs(quests_dir, exist_ok=True)

        # Group results by quest
        quest_results = {}
        for result in results:
            quest_name = Path(result['quest']).stem
            if quest_name not in quest_results:
                quest_results[quest_name] = []
            quest_results[quest_name].append(result)

        # Add quest metrics to benchmark summary
        for quest_name, quest_results_list in quest_results.items():
            benchmark_metrics['quests'].append({
                'name': quest_name,
                'results': [
                    {
                        'agent': {
                            'model': result['model'],
                            'template': result['template'],
                            'temperature': result['temperature']
                        },
                        'outcome': result['outcome'],
                        'error': result['error'],
                        'timestamp': result['timestamp'],
                        'steps': result['steps']
                    }
                    for result in quest_results_list
                ]
            })

            # Save quest-specific results
            quest_dir = os.path.join(quests_dir, quest_name)
            os.makedirs(quest_dir, exist_ok=True)
            output_file = os.path.join(quest_dir, f"{timestamp}.json")
            with open(output_file, 'w') as f:
                json.dump(quest_results_list, f, indent=2)

        # Save benchmark summary
        summary_file = os.path.join(config.output_dir, f"benchmark_{timestamp}.json")
        with open(summary_file, 'w') as f:
            json.dump(benchmark_metrics, f, indent=2)

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
        'total_errors': len([r for r in results if r['error']]),
        'total_timeouts': len([r for r in results if r['outcome'] == QuestOutcome.TIMEOUT.name]),
        'success_rate': 0,
        'error_rate': 0,
        'timeout_rate': 0
    }

    # Calculate per-model statistics
    models = {r['model'] for r in results}
    for model in sorted(models):
        model_results = [r for r in results if r['model'] == model]
        success = len([r for r in model_results if r['outcome'] == QuestOutcome.SUCCESS.name])
        failed = len([r for r in model_results if r['outcome'] == QuestOutcome.FAILURE.name])
        error = len([r for r in model_results if r['outcome'] in (QuestOutcome.ERROR.name, QuestOutcome.TIMEOUT.name)])
        timeout = len([r for r in model_results if r['outcome'] == QuestOutcome.TIMEOUT.name])
        total = len(model_results)

        summary['models'][model] = {
            'total_runs': total,
            'success': success,
            'success_rate': success/total if total > 0 else 0,
            'failed': failed,
            'failure_rate': failed/total if total > 0 else 0,
            'errors': error,
            'error_rate': error/total if total > 0 else 0,
            'timeouts': timeout,
            'timeout_rate': timeout/total if total > 0 else 0
        }

    # Calculate overall rates
    total = len(results)
    if total > 0:
        summary['success_rate'] = len([r for r in results if r['outcome'] == QuestOutcome.SUCCESS.name]) / total
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

    # Group by model
    models = {r['model'] for r in results}
    for model in sorted(models):
        model_results = [r for r in results if r['model'] == model]
        success = len([r for r in model_results if r['outcome'] == QuestOutcome.SUCCESS.name])
        failed = len([r for r in model_results if r['outcome'] == QuestOutcome.FAILURE.name])
        error = len([r for r in model_results if r['outcome'] in (QuestOutcome.ERROR.name, QuestOutcome.TIMEOUT.name)])
        timeout = len([r for r in model_results if r['outcome'] == QuestOutcome.TIMEOUT.name])
        total = len(model_results)

        print(f"\nModel: {model}")
        print(f"Total quests: {total}")
        print(f"Success: {success} ({success/total*100:.1f}%)")
        print(f"Failed: {failed} ({failed/total*100:.1f}%)")
        print(f"Error: {error} ({error/total*100:.1f}%)")
        print(f"Timeout: {timeout} ({timeout/total*100:.1f}%)")

    # List errors if any
    errors = [r for r in results if r['error']]
    if errors:
        print("\nErrors encountered:")
        print("=" * 80)
        for r in errors:
            print(f"{r['quest']} - {r['model']}: {r['error']}")