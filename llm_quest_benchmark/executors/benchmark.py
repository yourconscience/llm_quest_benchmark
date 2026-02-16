"""Benchmark executor for running multiple quests with multiple agents"""
import logging
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from llm_quest_benchmark.core.runner import run_quest_with_timeout
from llm_quest_benchmark.agents.agent_factory import create_agent
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.schemas.config import BenchmarkConfig
from llm_quest_benchmark.core.logging import DEFAULT_DB_PATH

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


def _emit_progress(progress_callback, payload: Dict[str, Any]) -> None:
    """Emit progress payload while preserving legacy callback signature."""
    if not progress_callback:
        return
    try:
        progress_callback(payload)
    except TypeError:
        quest = payload.get("quest")
        agent_id = payload.get("agent_id")
        if quest and agent_id:
            progress_callback(quest, agent_id)


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


def _load_benchmark_runs_from_db(benchmark_id: str, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Load DB runs associated with a benchmark id."""
    if not Path(db_path).exists():
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, quest_file, quest_name, start_time, end_time, agent_id,
                   agent_config, outcome, reward, run_duration, benchmark_id
            FROM runs
            WHERE benchmark_id = ?
            ORDER BY id
            """,
            (benchmark_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _write_benchmark_artifacts(config: BenchmarkConfig, results: List[Dict[str, Any]]) -> Optional[Path]:
    """Write benchmark-level manifest/config/summary artifacts."""
    if not config.output_dir:
        return None

    output_root = Path(config.output_dir)
    benchmark_dir = output_root / config.benchmark_id
    benchmark_dir.mkdir(exist_ok=True, parents=True)

    summary = {
        "name": config.name,
        "benchmark_id": config.benchmark_id,
        "timestamp": datetime.now().isoformat(),
        "quests": config.quests,
        "agents": [
            {
                "agent_id": agent.agent_id,
                "model": agent.model,
                "temperature": agent.temperature,
                "system_template": agent.system_template,
                "action_template": agent.action_template,
            }
            for agent in config.agents
        ],
        "results": results,
        "db_runs": _load_benchmark_runs_from_db(config.benchmark_id),
        "summary_stats": calculate_summary_stats(results),
    }

    with open(benchmark_dir / "benchmark_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    config_dump = {
        "quests": config.quests,
        "debug": config.debug,
        "quest_timeout": config.quest_timeout,
        "benchmark_timeout": config.benchmark_timeout,
        "output_dir": config.output_dir,
        "name": config.name,
        "renderer": config.renderer,
        "benchmark_id": config.benchmark_id,
        "max_quests": config.max_quests,
        "max_workers": config.max_workers,
        "agents": [
            {
                "model": agent.model,
                "system_template": agent.system_template,
                "action_template": agent.action_template,
                "temperature": agent.temperature,
                "skip_single": agent.skip_single,
                "debug": agent.debug,
            }
            for agent in config.agents
        ],
    }
    with open(benchmark_dir / "benchmark_config.json", "w", encoding="utf-8") as f:
        json.dump(config_dump, f, indent=2, ensure_ascii=False)

    return benchmark_dir


def run_benchmark(config: BenchmarkConfig, progress_callback=None) -> List[Dict[str, Any]]:
    """Run benchmark on a set of quests with multiple agents

    Args:
        config: Benchmark configuration
        progress_callback: Optional callback to report progress
        
    Returns:
        List of results for each quest/agent combination
    """
    # Generate a benchmark ID if not provided
    if not config.benchmark_id:
        config.benchmark_id = f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    if config.max_workers and config.max_workers > 1:
        logger.info("max_workers=%s is currently accepted but benchmark runs sequentially", config.max_workers)

    logger.info(f"Running benchmark with ID: {config.benchmark_id}")
    
    # Expand quest paths into actual quest files
    quest_files = get_quest_files(config.quests, config.max_quests)
    logger.info(f"Found {len(quest_files)} quests to run")
    
    # Print summary of what will be run
    logger.info(f"Running {len(quest_files)} quests with {len(config.agents)} agents")
    logger.info(f"Agents: {', '.join(a.agent_id for a in config.agents)}")
    
    # Collect results for each agent x quest combination.
    results = []

    total_runs = len(config.agents) * len(quest_files)
    run_index = 0

    for agent_config in config.agents:
        for quest_file in quest_files:
            run_index += 1
            quest_str = str(quest_file)
            quest_name = Path(quest_file).name
            
            logger.info(f"Agent {agent_config.agent_id} running quest {quest_name}")
            _emit_progress(
                progress_callback,
                {
                    "event": "pair_start",
                    "run_index": run_index,
                    "total_runs": total_runs,
                    "quest": quest_str,
                    "quest_name": quest_name,
                    "agent_id": agent_config.agent_id,
                    "model": agent_config.model,
                },
            )
            
            try:
                # Set the benchmark_id in agent_config for database tracking
                agent_config.benchmark_id = config.benchmark_id
                
                # Create agent
                agent = create_agent(
                    model=agent_config.model,
                    temperature=agent_config.temperature,
                    system_template=agent_config.system_template,
                    action_template=agent_config.action_template,
                    skip_single=agent_config.skip_single,
                    debug=agent_config.debug
                )
                
                # Run quest with timeout
                outcome = run_quest_with_timeout(
                    quest_str,
                    agent,
                    timeout=config.quest_timeout,
                    agent_config=agent_config
                )
                
                outcome_name = outcome.name if outcome else QuestOutcome.TIMEOUT.name
                timeout_error = None if outcome else f"Timed out after {config.quest_timeout} seconds"

                # Create result entry
                result = {
                    'quest': quest_str,
                    'model': agent_config.model,
                    'temperature': agent_config.temperature,
                    'template': agent_config.action_template,
                    'agent_id': agent_config.agent_id,
                    'outcome': outcome_name,
                    'reward': getattr(outcome, 'reward', 0.0),
                    'error': timeout_error
                }
                _emit_progress(
                    progress_callback,
                    {
                        "event": "pair_done",
                        "run_index": run_index,
                        "total_runs": total_runs,
                        "quest": quest_str,
                        "quest_name": quest_name,
                        "agent_id": agent_config.agent_id,
                        "model": agent_config.model,
                        "outcome": outcome_name,
                        "error": timeout_error,
                    },
                )
                
            except Exception as e:
                # Log the error but continue with other quests
                logger.error(f"Error running quest {quest_file} with agent {agent_config.agent_id}: {e}")
                
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
                _emit_progress(
                    progress_callback,
                    {
                        "event": "pair_done",
                        "run_index": run_index,
                        "total_runs": total_runs,
                        "quest": quest_str,
                        "quest_name": quest_name,
                        "agent_id": agent_config.agent_id,
                        "model": agent_config.model,
                        "outcome": QuestOutcome.ERROR.name,
                        "error": str(e),
                    },
                )
            results.append(result)

    artifact_dir = _write_benchmark_artifacts(config, results)
    if artifact_dir:
        logger.info("Benchmark artifacts saved to %s", artifact_dir)

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
