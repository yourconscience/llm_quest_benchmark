"""Benchmark executor for running multiple quests with multiple agents"""
import os
import sys
import logging
import json
import glob
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from typing import List, Dict, Any, Optional, Tuple

from llm_quest_benchmark.core.runner import run_quest_with_timeout
from llm_quest_benchmark.agents.agent_factory import create_agent
from llm_quest_benchmark.agents.llm_agent import LLMAgent
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.dataclasses.config import AgentConfig, BenchmarkConfig
from llm_quest_benchmark.core.time import calculate_benchmark_timeout, DEFAULT_QUEST_TIMEOUT
from llm_quest_benchmark.renderers.factory import create_renderer
from llm_quest_benchmark.renderers.progress import ProgressRenderer
from llm_quest_benchmark.core.logging import LogManager, QuestLogger
from llm_quest_benchmark.constants import DEFAULT_QUEST_TIMEOUT
from llm_quest_benchmark.dataclasses.config import BenchmarkConfig

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
    """Run benchmark on a set of quests with multiple agents"""
    # Initialize logging
    log_manager = LogManager()
    logger = log_manager.get_logger()
    quest_logger = QuestLogger(debug=config.debug)

    # Get quest files
    quest_files = []
    for quest_glob in config.quests:
        quest_files.extend(glob.glob(quest_glob))

    if not quest_files:
        raise ValueError(f"No quest files found matching patterns: {config.quests}")

    # Create agents
    agents = []
    for agent_config in config.agents:
        try:
            agent = create_agent(
                model=agent_config.model,
                system_template=agent_config.system_template,
                action_template=agent_config.action_template,
                temperature=agent_config.temperature,
                skip_single=agent_config.skip_single
            )
            agents.append((agent_config, agent))
        except Exception as e:
            logger.error(f"Failed to create agent with config {agent_config}: {e}")
            continue

    if not agents:
        raise ValueError("No valid agents created")

    # Create all tasks
    all_tasks = []
    for quest_file in quest_files:
        for agent_config, agent in agents:
            all_tasks.append((Path(quest_file), agent_config, agent))

    # Configure timeouts
    quest_timeout = config.quest_timeout or DEFAULT_QUEST_TIMEOUT
    benchmark_timeout = config.benchmark_timeout or (quest_timeout * len(all_tasks))

    # Initialize renderer
    renderer = create_renderer(config.renderer, debug=config.debug)

    # Initialize benchmark metrics
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
                'system_template': agent_config.system_template,
                'action_template': agent_config.action_template,
                'temperature': agent_config.temperature,
                'skip_single': agent_config.skip_single
            }
            for _, agent_config in agents
        ],
        'quests': [],
        'summary': {
            'total_quests': len(quest_files),
            'total_runs': len(all_tasks),
            'outcomes': {},
            'steps': {
                'total': 0,
                'average': 0,
                'by_model': {}
            }
        }
    }

    # Run tasks
    results = []
    with ThreadPoolExecutor(max_workers=config.max_workers) as executor:
        futures = []
        for quest_file, agent_config, agent in all_tasks:
            future = executor.submit(
                run_quest_with_timeout,
                quest_file=quest_file,
                agent=agent,
                timeout=quest_timeout,
                debug=config.debug
            )
            futures.append((quest_file, agent_config, future))

        # Process results as they complete
        for quest_file, agent_config, future in futures:
            try:
                result = future.result(timeout=quest_timeout)
                error_msg = None

                # Start recording metrics for this run
                quest_logger.start_quest_run(
                    quest_file=str(quest_file),
                    model=agent_config.model,
                    template=agent_config.system_template,
                    benchmark_name=config.name
                )

                # Record each step
                for step in result.get('steps', []):
                    quest_logger.record_step(step)

                # End run with outcome
                quest_logger.end_quest_run(
                    outcome=result.get('outcome'),
                    reward=result.get('reward', 0.0)
                )

            except TimeoutError:
                error_msg = "Quest timed out"
                result = {
                    'quest': str(quest_file),
                    'model': agent_config.model,
                    'outcome': 'TIMEOUT',
                    'error': error_msg
                }
            except Exception as e:
                error_msg = str(e)
                result = {
                    'quest': str(quest_file),
                    'model': agent_config.model,
                    'outcome': 'ERROR',
                    'error': error_msg
                }

            results.append(result)

            if isinstance(renderer, ProgressRenderer):
                renderer.update(
                    quest_name=quest_file.stem,
                    agent=str(agent_config),
                    outcome=QuestOutcome[result['outcome']],
                    error=error_msg,
                    llm_error=result.get('llm_error', False)
                )

            # Update benchmark metrics with outcomes and steps
            outcome = result['outcome']
            if outcome not in benchmark_metrics['summary']['outcomes']:
                benchmark_metrics['summary']['outcomes'][outcome] = 0
            benchmark_metrics['summary']['outcomes'][outcome] += 1

            # Track steps
            steps_count = len(result.get('steps', []))
            benchmark_metrics['summary']['steps']['total'] += steps_count

            # Track steps by model
            model = result['model']
            if model not in benchmark_metrics['summary']['steps']['by_model']:
                benchmark_metrics['summary']['steps']['by_model'][model] = {
                    'total': 0,
                    'count': 0,
                    'average': 0
                }
            benchmark_metrics['summary']['steps']['by_model'][model]['total'] += steps_count
            benchmark_metrics['summary']['steps']['by_model'][model]['count'] += 1

    # Close renderer
    renderer.close()

    # Calculate average steps
    total_runs = len(results)
    if total_runs > 0:
        benchmark_metrics['summary']['steps']['average'] = benchmark_metrics['summary']['steps']['total'] / total_runs

        # Calculate per-model averages
        for model_stats in benchmark_metrics['summary']['steps']['by_model'].values():
            if model_stats['count'] > 0:
                model_stats['average'] = model_stats['total'] / model_stats['count']

    # Save results if output dir specified
    if config.output_dir:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        metrics_root = Path(config.output_dir)
        metrics_root.mkdir(exist_ok=True)

        # Save benchmark summary
        summary_file = metrics_root / f"benchmark_{timestamp}.json"
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
        'total_llm_errors': len([r for r in results if r.get('llm_error', False)]),
        'success_rate': 0,
        'error_rate': 0,
        'timeout_rate': 0,
        'llm_error_rate': 0
    }

    # Calculate per-model statistics
    models = {r['model'] for r in results}
    for model in sorted(models):
        model_results = [r for r in results if r['model'] == model]
        success = len([r for r in model_results if r['outcome'] == QuestOutcome.SUCCESS.name])
        failed = len([r for r in model_results if r['outcome'] == QuestOutcome.FAILURE.name])
        error = len([r for r in model_results if r['outcome'] in (QuestOutcome.ERROR.name, QuestOutcome.TIMEOUT.name)])
        timeout = len([r for r in model_results if r['outcome'] == QuestOutcome.TIMEOUT.name])
        llm_errors = len([r for r in model_results if r.get('llm_error', False)])
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
            'timeout_rate': timeout/total if total > 0 else 0,
            'llm_errors': llm_errors,
            'llm_error_rate': llm_errors/total if total > 0 else 0
        }

    # Calculate overall rates
    total = len(results)
    if total > 0:
        summary['success_rate'] = len([r for r in results if r['outcome'] == QuestOutcome.SUCCESS.name]) / total
        summary['error_rate'] = summary['total_errors'] / total
        summary['timeout_rate'] = summary['total_timeouts'] / total
        summary['llm_error_rate'] = summary['total_llm_errors'] / total

    return summary


def print_summary(results: List[Dict[str, Any]]) -> None:
    """Print benchmark results summary

    Args:
        results (List[Dict[str, Any]]): List of benchmark results
    """
    print("\nResults Summary:")
    print("=" * 80)

    # Calculate total steps
    total_steps = sum(len(r.get('steps', [])) for r in results)
    steps_by_model = {}

    # Group by model
    models = {r['model'] for r in results}
    for model in sorted(models):
        model_results = [r for r in results if r['model'] == model]
        success = len([r for r in model_results if r['outcome'] == QuestOutcome.SUCCESS.name])
        failed = len([r for r in model_results if r['outcome'] == QuestOutcome.FAILURE.name])
        error = len([r for r in model_results if r['outcome'] in (QuestOutcome.ERROR.name, QuestOutcome.TIMEOUT.name)])
        timeout = len([r for r in model_results if r['outcome'] == QuestOutcome.TIMEOUT.name])
        llm_errors = len([r for r in model_results if r.get('llm_error', False)])
        total = len(model_results)

        # Calculate steps for this model
        model_steps = sum(len(r.get('steps', [])) for r in model_results)
        avg_steps = model_steps / total if total > 0 else 0
        steps_by_model[model] = (model_steps, avg_steps)

        print(f"\nModel: {model}")
        print(f"Total quests: {total}")
        print(f"Success: {success} ({success/total*100:.1f}%)")
        print(f"Failed: {failed} ({failed/total*100:.1f}%)")
        print(f"Error: {error} ({error/total*100:.1f}%)")
        print(f"Timeout: {timeout} ({timeout/total*100:.1f}%)")
        print(f"Total steps: {model_steps}")
        print(f"Average steps per quest: {avg_steps:.1f}")
        if isinstance(model, str) and ('gpt' in model.lower() or 'llm' in model.lower() or 'claude' in model.lower()):
            print(f"LLM Errors: {llm_errors} ({llm_errors/total*100:.1f}%)")

    # Print overall steps summary
    print("\nOverall Steps Summary:")
    print("=" * 80)
    print(f"Total steps across all models: {total_steps}")
    print(f"Average steps per quest: {total_steps/len(results):.1f}")

    # List errors if any
    errors = [r for r in results if r['error']]
    if errors:
        print("\nErrors encountered:")
        print("=" * 80)
        for r in errors:
            error_type = "LLM Error" if r.get('llm_error', False) else "Error"
            print(f"{r['quest']} - {r['model']}: {error_type} - {r['error']}")