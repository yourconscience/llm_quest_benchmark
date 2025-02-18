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
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.executors.benchmark_config import BenchmarkConfig, AgentConfig

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

    # Prepare tasks - each quest with each agent
    all_tasks: List[Tuple[Path, AgentConfig]] = [
        (quest, agent)
        for quest in quest_files
        for agent in config.agents
    ]

    # Run tasks in parallel
    results = []
    benchmark_metrics = {
        'timestamp': datetime.now().isoformat(),
        'config': {
            'timeout_seconds': config.timeout_seconds,
            'debug': config.debug,
            'max_workers': config.max_workers,
        },
        'agents': [
            {
                'model': agent.model,
                'template': agent.template,
                'temperature': agent.temperature,
                'skip_single': agent.skip_single
            }
            for agent in config.agents
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
                agent.model,
                agent.template,
                agent.temperature,
                config.timeout_seconds,
                config.debug,
                agent.skip_single,
                True  # Always run headless in benchmark
            ): (quest, agent)
            for quest, agent in all_tasks
        }

        # Wait for each future to complete with timeout
        for future in as_completed(future_to_task):
            quest, agent = future_to_task[future]
            try:
                result = future.result(timeout=config.timeout_seconds)
                results.append(result)
                status = 'SUCCESS' if result['outcome'] == QuestOutcome.SUCCESS.name else 'FAILED'
                error_msg = f" (Error: {result['error']})" if result['error'] else ""
                logger.info(f"{result['quest']} - {agent.model}: {status}{error_msg}")
            except TimeoutError:
                logger.error(f"Quest {quest} with {agent.model} timed out after {config.timeout_seconds}s")
                result = {
                    'quest': quest.name,
                    'model': agent.model,
                    'template': agent.template,
                    'temperature': agent.temperature,
                    'outcome': QuestOutcome.ERROR.name,
                    'error': f'Timeout after {config.timeout_seconds}s',
                    'timestamp': datetime.now().isoformat(),
                    'steps': []
                }
                results.append(result)
            except Exception as e:
                logger.error(f"Quest {quest} with {agent.model} failed: {e}")
                result = {
                    'quest': quest.name,
                    'model': agent.model,
                    'template': agent.template,
                    'temperature': agent.temperature,
                    'outcome': QuestOutcome.ERROR.name,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat(),
                    'steps': []
                }
                results.append(result)

    # Update benchmark metrics with outcomes
    for result in results:
        if result['outcome'] not in benchmark_metrics['summary']['outcomes']:
            benchmark_metrics['summary']['outcomes'][result['outcome']] = 0
        benchmark_metrics['summary']['outcomes'][result['outcome']] += 1

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
            benchmark_metrics['quests'].append({
                'name': quest_name,
                'agent': {
                    'model': result['model'],
                    'template': result['template'],
                    'temperature': result['temperature']
                },
                'outcome': result['outcome'],
                'error': result['error'],
                'timestamp': result['timestamp']
            })

        # Save quest-specific results
        for quest_name, quest_results_list in quest_results.items():
            quest_dir = os.path.join(quests_dir, quest_name)
            os.makedirs(quest_dir, exist_ok=True)

            output_file = os.path.join(quest_dir, f"benchmark_{timestamp}.jsonl")
            with open(output_file, 'w', encoding='utf-8') as f:
                for result in quest_results_list:
                    f.write(json.dumps(result, ensure_ascii=False) + '\n')
            logger.info(f"Results for quest {quest_name} saved to {output_file}")

        # Save benchmark metrics
        benchmarks_dir = os.path.join(config.output_dir, "benchmarks")
        os.makedirs(benchmarks_dir, exist_ok=True)
        benchmark_file = os.path.join(benchmarks_dir, f"benchmark_{timestamp}.json")
        with open(benchmark_file, 'w', encoding='utf-8') as f:
            json.dump(benchmark_metrics, f, indent=2, ensure_ascii=False)
        logger.info(f"Benchmark metrics saved to {benchmark_file}")

    return results


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
        error = len([r for r in model_results if r['outcome'] == QuestOutcome.ERROR.name])
        total = len(model_results)

        print(f"\nModel: {model}")
        print(f"Total quests: {total}")
        print(f"Success: {success} ({success/total*100:.1f}%)")
        print(f"Failed: {failed} ({failed/total*100:.1f}%)")
        print(f"Error: {error} ({error/total*100:.1f}%)")

    # List errors if any
    errors = [r for r in results if r['error']]
    if errors:
        print("\nErrors encountered:")
        print("=" * 80)
        for r in errors:
            print(f"{r['quest']} - {r['model']}: {r['error']}")