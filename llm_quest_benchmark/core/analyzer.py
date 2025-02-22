"""Quest run analyzer for metrics analysis"""
import json
import logging
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from llm_quest_benchmark.core.logging import LogManager
from llm_quest_benchmark.renderers.benchmark_result import BenchmarkResultRenderer

# Initialize logging
log_manager = LogManager()
log = log_manager.get_logger()


def analyze_quest_run(
    quest_name: str,
    db_path: Path,
    debug: bool = False,
) -> Dict[str, Any]:
    """Analyze metrics for a specific quest from database.

    Args:
        quest_name: Name of the quest to analyze
        db_path: Path to SQLite database
        debug: Enable debug logging and output

    Returns:
        Dict containing analysis results

    Raises:
        ValueError: If quest not found or database error
    """
    log_manager.setup(debug)

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get all runs for this quest
        cursor.execute('''
            SELECT id, start_time, end_time, model, template, outcome, reward
            FROM runs
            WHERE quest_name = ?
            ORDER BY start_time DESC
        ''', (quest_name,))
        runs = cursor.fetchall()

        if not runs:
            raise ValueError(f"No runs found for quest: {quest_name}")

        # Prepare analysis results
        results = {
            "quest_name": quest_name,
            "total_runs": len(runs),
            "outcomes": {"SUCCESS": 0, "FAILURE": 0},
            "runs": []
        }

        # Process each run
        for run in runs:
            run_id, start_time, end_time, model, template, outcome, reward = run
            results["outcomes"][outcome] = results["outcomes"].get(outcome, 0) + 1

            # Get steps for this run
            cursor.execute('''
                SELECT step, observation, choices, action, reward, llm_response
                FROM steps
                WHERE run_id = ?
                ORDER BY step
            ''', (run_id,))
            steps = cursor.fetchall()

            run_data = {
                "start_time": start_time,
                "end_time": end_time,
                "model": model,
                "template": template,
                "outcome": outcome,
                "reward": reward,
                "steps": []
            }

            for step in steps:
                step_num, obs, choices_json, action, step_reward, llm_response = step
                choices = json.loads(choices_json)
                run_data["steps"].append({
                    "step": step_num,
                    "observation": obs,
                    "choices": choices,
                    "action": action,
                    "reward": step_reward,
                    "llm_response": llm_response
                })

            results["runs"].append(run_data)

        conn.close()
        return results

    except Exception as e:
        log.exception(f"Error analyzing quest run: {e}")
        raise ValueError(f"Error analyzing quest run: {e}")


def analyze_benchmark(
    db_path: Path,
    benchmark_name: Optional[str] = None,
    debug: bool = False,
) -> Dict[str, Any]:
    """Analyze benchmark results from database.

    Args:
        db_path: Path to SQLite database
        benchmark_name: Optional name of benchmark to analyze
        debug: Enable debug logging and output

    Returns:
        Dict containing analysis results

    Raises:
        ValueError: If no data found or database error
    """
    log_manager.setup(debug)

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Base query conditions
        where_clause = "WHERE 1=1"
        params = []
        if benchmark_name:
            where_clause += " AND benchmark_name = ?"
            params.append(benchmark_name)

        # Get overall statistics
        cursor.execute(f'''
            SELECT
                COUNT(*) as total_runs,
                COUNT(CASE WHEN outcome = 'SUCCESS' THEN 1 END) as successes,
                COUNT(CASE WHEN outcome = 'FAILURE' THEN 1 END) as failures,
                AVG(CASE WHEN outcome = 'SUCCESS' THEN reward END) as avg_success_reward
            FROM runs
            {where_clause}
        ''', params)
        stats = cursor.fetchone()
        total_runs, successes, failures, avg_success_reward = stats

        if total_runs == 0:
            raise ValueError(f"No benchmark data found{' for ' + benchmark_name if benchmark_name else ''}")

        # Get per-model statistics
        cursor.execute(f'''
            SELECT
                model,
                COUNT(*) as runs,
                COUNT(CASE WHEN outcome = 'SUCCESS' THEN 1 END) as successes,
                AVG(CASE WHEN outcome = 'SUCCESS' THEN reward END) as avg_reward
            FROM runs
            {where_clause}
            GROUP BY model
        ''', params)
        model_stats = cursor.fetchall()

        # Get per-quest statistics
        cursor.execute(f'''
            SELECT
                quest_name,
                COUNT(*) as runs,
                COUNT(CASE WHEN outcome = 'SUCCESS' THEN 1 END) as successes
            FROM runs
            {where_clause}
            GROUP BY quest_name
        ''', params)
        quest_stats = cursor.fetchall()

        # Prepare results
        results = {
            "summary": {
                "total_runs": total_runs,
                "success_rate": (successes / total_runs * 100) if total_runs > 0 else 0,
                "avg_success_reward": avg_success_reward or 0,
                "outcomes": {
                    "SUCCESS": successes,
                    "FAILURE": failures
                }
            },
            "models": [{
                "name": model,
                "runs": runs,
                "success_rate": (successes / runs * 100) if runs > 0 else 0,
                "avg_reward": avg_reward or 0
            } for model, runs, successes, avg_reward in model_stats],
            "quests": [{
                "name": quest,
                "runs": runs,
                "success_rate": (successes / runs * 100) if runs > 0 else 0
            } for quest, runs, successes in quest_stats]
        }

        if benchmark_name:
            results["benchmark_name"] = benchmark_name

        conn.close()

        # Create renderer and display results
        renderer = BenchmarkResultRenderer(debug=debug)
        renderer.render_benchmark_results(results, debug=debug)

        return results

    except Exception as e:
        log.exception(f"Error analyzing benchmark: {e}")
        raise ValueError(f"Error analyzing benchmark: {e}")