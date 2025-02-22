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
from llm_quest_benchmark.agents.llm_agent import LLMAgent
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.dataclasses.config import AgentConfig, BenchmarkConfig
from llm_quest_benchmark.core.time import calculate_benchmark_timeout, DEFAULT_QUEST_TIMEOUT
from llm_quest_benchmark.renderers.factory import create_renderer
from llm_quest_benchmark.renderers.progress import ProgressRenderer

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
            agent = create_agent(model=agent_config.model,
                                 template=agent_config.template,
                                 temperature=agent_config.temperature,
                                 debug=config.debug,
                                 skip_single=agent_config.skip_single
                                 )
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

    # Initialize renderer based on agent type and mode
    renderer = create_renderer(
        agent=agents[0][0],  # Use first agent to determine renderer type
        debug=config.debug,
        total_quests=len(quest_files),
        total_runs=len(all_tasks)
    )

    quest_timeout = config.quest_timeout or DEFAULT_QUEST_TIMEOUT
    # Calculate appropriate timeouts
    benchmark_timeout = calculate_benchmark_timeout(
        num_quests=len(quest_files),
        num_agents=len(config.agents),
        num_workers=config.max_workers,
        quest_timeout=quest_timeout
    )

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
        # Submit all tasks
        future_to_task = {
            executor.submit(
                run_quest_with_timeout,
                str(quest),
                agent,
                timeout=quest_timeout,  # Use calculated quest timeout
                debug=config.debug,
                renderer=renderer,  # Pass the renderer
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

                # Track LLM errors
                if isinstance(agent, LLMAgent):
                    result['llm_error'] = getattr(agent, 'last_error', None) is not None

                results.append(result)

                outcome = QuestOutcome[result['outcome']]
                if isinstance(renderer, ProgressRenderer):
                    renderer.update(
                        quest_name=quest.stem,
                        agent=str(agent_config),
                        outcome=outcome,
                        error=result.get('error'),
                        llm_error=result.get('llm_error', False)
                    )
                else:
                    status = 'SUCCESS' if outcome == QuestOutcome.SUCCESS else 'FAILED'
                    error_msg = f" (Error: {result['error']})" if result.get('error') else ""
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
                    'steps': [],
                    'llm_error': isinstance(agent, LLMAgent) and getattr(agent, 'last_error', None) is not None
                }
                results.append(result)

                if isinstance(renderer, ProgressRenderer):
                    renderer.update(
                        quest_name=quest.stem,
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

        # Create metrics root directory
        metrics_root = Path(config.output_dir)
        metrics_root.mkdir(exist_ok=True)

        # Group results by quest
        quest_results = {}
        for result in results:
            quest_name = Path(result['quest']).stem
            if quest_name not in quest_results:
                quest_results[quest_name] = []
            quest_results[quest_name].append(result)

        # Add quest metrics to benchmark summary and save per-quest results
        for quest_name, quest_results_list in quest_results.items():
            # Create quest-specific directory
            quest_dir = metrics_root / quest_name
            quest_dir.mkdir(exist_ok=True)

            # Create run-specific directory with timestamp
            run_dir = quest_dir / f"run_{timestamp}"
            run_dir.mkdir(exist_ok=True)

            # Create quest summary
            quest_summary = {
                'name': quest_name,
                'timestamp': timestamp,
                'total_runs': len(quest_results_list),
                'outcomes': {},
                'results': quest_results_list
            }

            # Calculate quest-specific outcomes
            for result in quest_results_list:
                outcome = result['outcome']
                if outcome not in quest_summary['outcomes']:
                    quest_summary['outcomes'][outcome] = 0
                quest_summary['outcomes'][outcome] += 1

            # Save quest-specific results
            output_file = run_dir / "metrics.json"
            with open(output_file, 'w') as f:
                json.dump(quest_summary, f, indent=2)

            # Add to benchmark metrics
            benchmark_metrics['quests'].append(quest_summary)

        # Save benchmark summary in the root metrics directory
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