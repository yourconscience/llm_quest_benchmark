"""Quest run analyzer for metrics analysis"""
import csv
import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
        cursor.execute(
            '''
            SELECT id, start_time, end_time, model, template, outcome, reward, agent_id, agent_config
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
            "outcomes": {
                "SUCCESS": 0,
                "FAILURE": 0
            },
            "runs": []
        }

        # Process each run
        for run in runs:
            run_id, start_time, end_time, model, template, outcome, reward, agent_id, agent_config = run
            results["outcomes"][outcome] = results["outcomes"].get(outcome, 0) + 1

            # Get steps for this run
            cursor.execute(
                '''
                SELECT step, observation, choices, action, reward, llm_response
                FROM steps
                WHERE run_id = ?
                ORDER BY step
            ''', (run_id,))
            steps = cursor.fetchall()

            run_data = {
                "id": run_id,
                "start_time": start_time,
                "end_time": end_time,
                "model": model,
                "template": template,
                "outcome": outcome,
                "reward": reward,
                "agent_id": agent_id,
                "agent_config": json.loads(agent_config) if agent_config else {},
                "steps": []
            }

            # Extract memory and tool info
            if run_data["agent_config"]:
                memory_config = run_data["agent_config"].get("memory", {})
                if memory_config:
                    run_data["memory_type"] = memory_config.get("type", "none")
                    run_data["memory_size"] = memory_config.get("max_history", 0)
                run_data["tools"] = run_data["agent_config"].get("tools", [])

            for step in steps:
                step_num, obs, choices_json, action, step_reward, llm_response = step
                choices = json.loads(choices_json) if choices_json else []
                step_data = {
                    "step": step_num,
                    "observation": obs,
                    "choices": choices,
                    "action": action,
                    "reward": step_reward,
                    "llm_response": json.loads(llm_response) if llm_response else {}
                }

                # Check for tool use in llm_response
                if step_data["llm_response"] and isinstance(step_data["llm_response"], dict):
                    if "tool_type" in step_data["llm_response"]:
                        step_data["tool_used"] = True
                        step_data["tool_type"] = step_data["llm_response"].get("tool_type")
                        step_data["tool_query"] = step_data["llm_response"].get("tool_query")
                        step_data["tool_result"] = step_data["llm_response"].get(
                            "tool_result", "No result")

                run_data["steps"].append(step_data)

            results["runs"].append(run_data)

        conn.close()

        # Log results to CSV file for metrics
        log_quest_results_to_csv(results)

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
        conn.row_factory = sqlite3.Row  # Enable column access by name
        cursor = conn.cursor()

        # Base query conditions
        where_clause = "WHERE 1=1"
        params = []
        if benchmark_name:
            where_clause += " AND benchmark_name = ?"
            params.append(benchmark_name)

        # Get overall statistics
        cursor.execute(
            f'''
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
            raise ValueError(
                f"No benchmark data found{' for ' + benchmark_name if benchmark_name else ''}")

        # Get per-model statistics
        cursor.execute(
            f'''
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
        cursor.execute(
            f'''
            SELECT
                quest_name,
                COUNT(*) as runs,
                COUNT(CASE WHEN outcome = 'SUCCESS' THEN 1 END) as successes
            FROM runs
            {where_clause}
            GROUP BY quest_name
        ''', params)
        quest_stats = cursor.fetchall()

        # Get all runs for detailed analysis
        cursor.execute(
            f'''
            SELECT *
            FROM runs
            {where_clause}
            ORDER BY quest_name, model
        ''', params)
        all_runs = cursor.fetchall()

        # Prepare detailed run data for metrics
        detailed_runs = []
        for run in all_runs:
            run_dict = dict(run)

            # Parse agent_config if present
            if run_dict['agent_config']:
                config = json.loads(run_dict['agent_config'])

                # Extract memory and tool info if available
                memory_config = config.get('memory', {})
                if memory_config:
                    run_dict['memory_type'] = memory_config.get('type', 'none')
                    run_dict['memory_size'] = memory_config.get('max_history', 0)
                else:
                    run_dict['memory_type'] = 'none'
                    run_dict['memory_size'] = 0

                run_dict['tools'] = config.get('tools', [])
            else:
                run_dict['memory_type'] = 'none'
                run_dict['memory_size'] = 0
                run_dict['tools'] = []

            # Get step count for the run
            cursor.execute(
                '''
                SELECT COUNT(*) as step_count
                FROM steps
                WHERE run_id = ?
            ''', (run_dict['id'],))
            step_result = cursor.fetchone()
            if step_result:
                run_dict['step_count'] = step_result[0]
            else:
                run_dict['step_count'] = 0

            detailed_runs.append(run_dict)

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
            } for quest, runs, successes in quest_stats],
            "detailed_runs": detailed_runs
        }

        if benchmark_name:
            results["benchmark_name"] = benchmark_name

        conn.close()

        # Create renderer and display results
        renderer = BenchmarkResultRenderer(debug=debug)
        renderer.render_benchmark_results(results, debug=debug)

        # Log benchmark results to CSV for metrics
        log_benchmark_results_to_csv(detailed_runs, benchmark_name)

        return results

    except Exception as e:
        log.exception(f"Error analyzing benchmark: {e}")
        raise ValueError(f"Error analyzing benchmark: {e}")


def log_quest_results_to_csv(results: Dict[str, Any]) -> None:
    """Log quest run results to CSV file for metrics analysis

    Args:
        results (Dict[str, Any]): Quest run results
    """
    if not results or not results.get('runs'):
        return

    # Ensure metrics directory exists
    metrics_dir = Path("metrics/quest_logs")
    metrics_dir.mkdir(parents=True, exist_ok=True)

    # Create CSV filename with quest name
    quest_name = results['quest_name'].replace('.qm', '').replace('/', '_')
    csv_file = metrics_dir / f"{quest_name}_metrics.csv"

    # Create file with headers if it doesn't exist
    file_exists = csv_file.exists()

    with open(csv_file, mode='a', newline='') as f:
        fieldnames = [
            'run_id', 'timestamp', 'quest_name', 'outcome', 'reward', 'steps_taken', 'agent_id',
            'model', 'memory_type', 'memory_size', 'tools'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        # Write header if file is new
        if not file_exists:
            writer.writeheader()

        # Write each run
        for run in results['runs']:
            # Extract memory info if available
            memory_type = run.get('memory_type', 'none')
            memory_size = run.get('memory_size', 0)

            # Get tools info
            tools = ', '.join(run.get('tools', [])) if run.get('tools') else 'none'

            # Count steps
            steps_taken = len(run.get('steps', []))

            # Write row
            writer.writerow({
                'run_id': run['id'],
                'timestamp': run['start_time'],
                'quest_name': results['quest_name'],
                'outcome': run.get('outcome', 'unknown'),
                'reward': run.get('reward', 0),
                'steps_taken': steps_taken,
                'agent_id': run.get('agent_id', 'unknown'),
                'model': run.get('model', 'unknown'),
                'memory_type': memory_type,
                'memory_size': memory_size,
                'tools': tools
            })


def log_benchmark_results_to_csv(runs: List[Dict[str, Any]],
                                 benchmark_id: Optional[str] = None) -> None:
    """Log benchmark results to CSV file for metrics analysis

    Args:
        runs (List[Dict[str, Any]]): Benchmark results
        benchmark_id (Optional[str]): Benchmark ID
    """
    if not runs:
        return

    # Ensure metrics directory exists
    metrics_dir = Path("metrics/benchmark_logs")
    metrics_dir.mkdir(parents=True, exist_ok=True)

    # Create CSV filename with benchmark ID or timestamp
    if benchmark_id:
        csv_file = metrics_dir / f"benchmark_{benchmark_id}.csv"
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_file = metrics_dir / f"benchmark_{timestamp}.csv"

    # Create file with headers if it doesn't exist
    file_exists = csv_file.exists()

    with open(csv_file, mode='a', newline='') as f:
        fieldnames = [
            'run_id', 'timestamp', 'quest_name', 'benchmark_id', 'outcome', 'reward', 'agent_id',
            'model', 'memory_type', 'memory_size', 'tools', 'steps_taken'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        # Write header if file is new
        if not file_exists:
            writer.writeheader()

        # Write each run
        for run in runs:
            # Skip runs without benchmark_id if specific benchmark_id was requested
            if benchmark_id and run.get('benchmark_id') != benchmark_id:
                continue

            # Extract memory info
            memory_type = run.get('memory_type', 'none')
            memory_size = run.get('memory_size', 0)

            # Get tools info
            tools = ', '.join(run.get('tools', [])) if run.get('tools') else 'none'

            # Get step count
            steps_taken = run.get('step_count', 0)

            # Write row
            writer.writerow({
                'run_id': run.get('id', 0),
                'timestamp': run.get('start_time', ''),
                'quest_name': run.get('quest_name', 'unknown'),
                'benchmark_id': run.get('benchmark_id', ''),
                'outcome': run.get('outcome', 'unknown'),
                'reward': run.get('reward', 0),
                'agent_id': run.get('agent_id', 'unknown'),
                'model': run.get('model', 'unknown'),
                'memory_type': memory_type,
                'memory_size': memory_size,
                'tools': tools,
                'steps_taken': steps_taken
            })


def generate_memory_tool_report():
    """Generate a report of memory and tool usage metrics"""
    # Ensure metrics directories exist
    metrics_dir = Path("metrics")
    quest_logs_dir = metrics_dir / "quest_logs"
    benchmark_logs_dir = metrics_dir / "benchmark_logs"
    reports_dir = metrics_dir / "reports"

    for directory in [metrics_dir, quest_logs_dir, benchmark_logs_dir, reports_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    # Initialize report data
    report = {
        "timestamp": datetime.now().isoformat(),
        "memory_analysis": {
            "none": {
                "total_runs": 0,
                "success_rate": 0,
                "avg_steps": 0
            },
            "message_history": {
                "total_runs": 0,
                "success_rate": 0,
                "avg_steps": 0
            },
            "summary": {
                "total_runs": 0,
                "success_rate": 0,
                "avg_steps": 0
            }
        },
        "tools_analysis": {
            "with_tools": {
                "total_runs": 0,
                "success_rate": 0,
                "avg_steps": 0
            },
            "without_tools": {
                "total_runs": 0,
                "success_rate": 0,
                "avg_steps": 0
            }
        },
        "quests": {}
    }

    # Process quest log files
    for csv_file in quest_logs_dir.glob("*.csv"):
        if not csv_file.exists() or csv_file.stat().st_size == 0:
            continue

        quest_name = csv_file.stem.replace("_metrics", "")
        report["quests"][quest_name] = {
            "runs": 0,
            "memory_types": {
                "none": 0,
                "message_history": 0,
                "summary": 0
            },
            "tools": {
                "with": 0,
                "without": 0
            },
            "outcomes": {
                "SUCCESS": 0,
                "FAILURE": 0,
                "other": 0
            }
        }

        # Read CSV file
        with open(csv_file, newline='') as f:
            reader = csv.DictReader(f)

            memory_stats = {
                "none": {
                    "total": 0,
                    "success": 0,
                    "steps": []
                },
                "message_history": {
                    "total": 0,
                    "success": 0,
                    "steps": []
                },
                "summary": {
                    "total": 0,
                    "success": 0,
                    "steps": []
                }
            }

            tools_stats = {
                "with_tools": {
                    "total": 0,
                    "success": 0,
                    "steps": []
                },
                "without_tools": {
                    "total": 0,
                    "success": 0,
                    "steps": []
                }
            }

            for row in reader:
                # Count total runs
                report["quests"][quest_name]["runs"] += 1

                # Track outcome
                outcome = row.get('outcome', 'unknown').upper()
                if outcome in ["SUCCESS", "FAILURE"]:
                    report["quests"][quest_name]["outcomes"][outcome] += 1
                else:
                    report["quests"][quest_name]["outcomes"]["other"] += 1

                # Get memory type
                memory_type = row.get('memory_type', 'none')
                if memory_type not in memory_stats:
                    memory_type = 'none'

                # Update memory stats
                memory_stats[memory_type]["total"] += 1
                report["quests"][quest_name]["memory_types"][memory_type] += 1

                if outcome == "SUCCESS":
                    memory_stats[memory_type]["success"] += 1

                # Track steps
                try:
                    steps = int(row.get('steps_taken', 0))
                    memory_stats[memory_type]["steps"].append(steps)
                except (ValueError, TypeError):
                    pass

                # Update tool stats
                has_tools = row.get('tools', '').lower() not in ['', 'none']
                tool_category = "with_tools" if has_tools else "without_tools"

                tools_stats[tool_category]["total"] += 1
                report["quests"][quest_name]["tools"]["with" if has_tools else "without"] += 1

                if outcome == "SUCCESS":
                    tools_stats[tool_category]["success"] += 1

                try:
                    steps = int(row.get('steps_taken', 0))
                    tools_stats[tool_category]["steps"].append(steps)
                except (ValueError, TypeError):
                    pass

            # Update summary stats for memory types
            for memory_type, stats in memory_stats.items():
                if stats["total"] > 0:
                    success_rate = (stats["success"] / stats["total"]) * 100
                    avg_steps = sum(stats["steps"]) / len(stats["steps"]) if stats["steps"] else 0

                    # Update quest stats
                    if quest_name not in report["memory_analysis"]:
                        report["memory_analysis"][quest_name] = {}

                    report["memory_analysis"][quest_name][memory_type] = {
                        "total_runs": stats["total"],
                        "success_rate": success_rate,
                        "avg_steps": avg_steps
                    }

                    # Update overall stats
                    report["memory_analysis"][memory_type]["total_runs"] += stats["total"]
                    total_success = report["memory_analysis"][memory_type]["success_rate"] * \
                                   report["memory_analysis"][memory_type]["total_runs"]
                    new_total = report["memory_analysis"][memory_type]["total_runs"] + stats["total"]

                    if new_total > 0:
                        report["memory_analysis"][memory_type]["success_rate"] = \
                            (total_success + success_rate * stats["total"]) / new_total

                    total_steps = report["memory_analysis"][memory_type]["avg_steps"] * \
                                 report["memory_analysis"][memory_type]["total_runs"]

                    if new_total > 0:
                        report["memory_analysis"][memory_type]["avg_steps"] = \
                            (total_steps + avg_steps * stats["total"]) / new_total

            # Update summary stats for tools
            for tool_category, stats in tools_stats.items():
                if stats["total"] > 0:
                    success_rate = (stats["success"] / stats["total"]) * 100
                    avg_steps = sum(stats["steps"]) / len(stats["steps"]) if stats["steps"] else 0

                    # Update quest stats
                    if quest_name not in report["tools_analysis"]:
                        report["tools_analysis"][quest_name] = {}

                    report["tools_analysis"][quest_name][tool_category] = {
                        "total_runs": stats["total"],
                        "success_rate": success_rate,
                        "avg_steps": avg_steps
                    }

                    # Update overall stats
                    report["tools_analysis"][tool_category]["total_runs"] += stats["total"]
                    total_success = report["tools_analysis"][tool_category]["success_rate"] * \
                                   report["tools_analysis"][tool_category]["total_runs"]
                    new_total = report["tools_analysis"][tool_category]["total_runs"] + stats[
                        "total"]

                    if new_total > 0:
                        report["tools_analysis"][tool_category]["success_rate"] = \
                            (total_success + success_rate * stats["total"]) / new_total

                    total_steps = report["tools_analysis"][tool_category]["avg_steps"] * \
                                 report["tools_analysis"][tool_category]["total_runs"]

                    if new_total > 0:
                        report["tools_analysis"][tool_category]["avg_steps"] = \
                            (total_steps + avg_steps * stats["total"]) / new_total

    # Generate improvement metrics
    if report["memory_analysis"]["none"]["total_runs"] > 0:
        base_success = report["memory_analysis"]["none"]["success_rate"]
        report["memory_improvements"] = {
            "message_history_success_improvement":
                ((report["memory_analysis"]["message_history"]["success_rate"] - base_success) /
                 base_success *
                 100) if report["memory_analysis"]["message_history"]["total_runs"] > 0 else 0,
            "summary_success_improvement":
                ((report["memory_analysis"]["summary"]["success_rate"] - base_success) /
                 base_success *
                 100) if report["memory_analysis"]["summary"]["total_runs"] > 0 else 0
        }

    if report["tools_analysis"]["without_tools"]["total_runs"] > 0:
        base_success = report["tools_analysis"]["without_tools"]["success_rate"]
        report["tools_improvements"] = {
            "tools_success_improvement":
                ((report["tools_analysis"]["with_tools"]["success_rate"] - base_success) /
                 base_success *
                 100) if report["tools_analysis"]["with_tools"]["total_runs"] > 0 else 0
        }

    # Save report to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = reports_dir / f"memory_tool_report_{timestamp}.json"

    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)

    log.info(f"Generated memory and tool metrics report: {report_file}")
    return report
