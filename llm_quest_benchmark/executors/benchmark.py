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
from llm_quest_benchmark.schemas.config import AgentConfig, BenchmarkConfig
from llm_quest_benchmark.core.time import calculate_benchmark_timeout, DEFAULT_QUEST_TIMEOUT
from llm_quest_benchmark.renderers.factory import create_renderer
from llm_quest_benchmark.renderers.progress import ProgressRenderer
from llm_quest_benchmark.core.logging import LogManager, QuestLogger
from llm_quest_benchmark.constants import DEFAULT_QUEST_TIMEOUT

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


def run_benchmark(config: BenchmarkConfig, progress_callback=None) -> List[Dict[str, Any]]:
    """Run benchmark on a set of quests with multiple agents"""
    results = []
    benchmark_metrics = {
        'name': config.name,
        'timestamp': datetime.now().isoformat(),
        'quests': [],
        'agents': []
    }

    # Create logger for benchmark
    logger = QuestLogger(debug=config.debug)

    for quest_file in config.quests:
        quest_metrics = {'quest': quest_file, 'runs': []}

        for agent_config in config.agents:
            # Get agent_id from agent_config
            agent_id = agent_config.agent_id

            # Create agent
            agent = create_agent(
                model=agent_config.model,
                temperature=agent_config.temperature,
                system_template=agent_config.system_template,
                action_template=agent_config.action_template,
                skip_single=agent_config.skip_single,
                debug=agent_config.debug
            )

            logger.logger.info(f"Running {quest_file} with agent {agent_id}")

            try:
                # Run quest with timeout
                outcome = run_quest_with_timeout(
                    quest_file,
                    agent,
                    timeout=config.quest_timeout,
                    agent_config=agent_config
                )
                
                # Call progress callback if provided
                if progress_callback:
                    progress_callback(quest_file, agent_id)

                if outcome:
                    result = {
                        'quest': quest_file,
                        'model': agent_config.model,
                        'temperature': agent_config.temperature,
                        'template': agent_config.system_template,
                        'agent_id': agent_id,
                        'outcome': outcome.name if outcome else None,
                        'reward': getattr(outcome, 'reward', 0.0)
                    }
                    results.append(result)
                    quest_metrics['runs'].append(result)

            except Exception as e:
                logger.logger.error(f"Error running quest {quest_file} with agent {agent_id}: {e}")
                result = {
                    'quest': quest_file,
                    'model': agent_config.model,
                    'temperature': agent_config.temperature,
                    'template': agent_config.system_template,
                    'agent_id': agent_id,
                    'outcome': QuestOutcome.ERROR.name,
                    'error': str(e)
                }
                results.append(result)
                quest_metrics['runs'].append(result)

        benchmark_metrics['quests'].append(quest_metrics)

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