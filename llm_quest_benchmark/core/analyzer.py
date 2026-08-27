"""Quest run analyzer for schema-v2 metrics analysis"""

import json
import sqlite3
from pathlib import Path
from typing import Any

from llm_quest_benchmark.core.logging import LogManager, verify_v2_schema
from llm_quest_benchmark.renderers.benchmark_result import BenchmarkResultRenderer
from llm_quest_benchmark.schemas.records import QuestTransition

# Initialize logging
log_manager = LogManager()
log = log_manager.get_logger()


def _json_field(value: Any, default: Any = None) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def load_transitions(conn: sqlite3.Connection, run_id: int) -> list[QuestTransition]:
    """Load canonical transitions for one run."""
    rows = conn.execute(
        """
        SELECT transition_index, before_state, action, after_state, response,
               usage, progress, provenance, replay_status, reasoning_mode
        FROM transitions
        WHERE run_id = ?
        ORDER BY transition_index
        """,
        (run_id,),
    ).fetchall()

    transitions = []
    for row in rows:
        (index, before, action, after, response, usage, progress, provenance, replay_status, reasoning_mode) = row
        transitions.append(
            QuestTransition.from_dict(
                {
                    "index": index,
                    "before": _json_field(before, {}),
                    "action": _json_field(action, {}),
                    "after": _json_field(after, {}),
                    "response": _json_field(response),
                    "usage": _json_field(usage, {}),
                    "progress": _json_field(progress, {}),
                    "provenance": provenance,
                    "replay_status": replay_status,
                    "reasoning_mode": reasoning_mode,
                }
            )
        )
    return transitions


def analyze_quest_run(
    quest_name: str,
    db_path: Path,
    debug: bool = False,
) -> dict[str, Any]:
    """Analyze metrics for a specific quest from the schema-v2 database.

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
        try:
            if not verify_v2_schema(conn):
                raise ValueError(f"No runs found for quest: {quest_name}")
            runs = conn.execute(
                """
                SELECT id, start_time, end_time, agent_id, treatment, treatment_signature,
                       outcome, reward, transcript_diagnostics, progress
                FROM runs
                WHERE quest_name = ?
                ORDER BY start_time DESC
                """,
                (quest_name,),
            ).fetchall()

            if not runs:
                raise ValueError(f"No runs found for quest: {quest_name}")

            results: dict[str, Any] = {
                "quest_name": quest_name,
                "total_runs": len(runs),
                "outcomes": {"SUCCESS": 0, "FAILURE": 0},
                "runs": [],
            }

            for run in runs:
                (
                    run_id,
                    start_time,
                    end_time,
                    agent_id,
                    treatment_json,
                    treatment_signature,
                    outcome,
                    reward,
                    diagnostics_json,
                    progress_json,
                ) = run
                results["outcomes"][outcome] = results["outcomes"].get(outcome, 0) + 1
                treatment = _json_field(treatment_json, {})
                transitions = load_transitions(conn, run_id)

                results["runs"].append(
                    {
                        "id": run_id,
                        "start_time": start_time,
                        "end_time": end_time,
                        "agent_id": agent_id,
                        "model": treatment.get("model", "unknown"),
                        "harness": treatment.get("harness", "unknown"),
                        "treatment_signature": treatment_signature,
                        "outcome": outcome,
                        "reward": reward,
                        "transcript_diagnostics": _json_field(diagnostics_json, {}),
                        "progress": _json_field(progress_json, {}),
                        "transitions": [t.to_dict() for t in transitions],
                    }
                )

            return results
        finally:
            conn.close()

    except ValueError:
        raise
    except Exception as e:
        log.exception(f"Error analyzing quest run: {e}")
        raise ValueError(f"Error analyzing quest run: {e}")


def analyze_benchmark(
    db_path: Path,
    benchmark_id: str | None = None,
    debug: bool = False,
) -> dict[str, Any]:
    """Analyze benchmark results from the schema-v2 database.

    Args:
        db_path: Path to SQLite database
        benchmark_id: Optional benchmark id to analyze
        debug: Enable debug logging and output

    Returns:
        Dict containing analysis results

    Raises:
        ValueError: If no data found or database error
    """
    log_manager.setup(debug)

    try:
        conn = sqlite3.connect(db_path)
        try:
            if not verify_v2_schema(conn):
                raise ValueError(f"No benchmark data found{' for ' + benchmark_id if benchmark_id else ''}")
            where_clause = "WHERE 1=1"
            params: list[Any] = []
            if benchmark_id:
                where_clause += " AND benchmark_id = ?"
                params.append(benchmark_id)

            stats = conn.execute(
                f"""
                SELECT
                    COUNT(*) as total_runs,
                    COUNT(CASE WHEN outcome = 'SUCCESS' THEN 1 END) as successes,
                    COUNT(CASE WHEN outcome = 'FAILURE' THEN 1 END) as failures,
                    AVG(CASE WHEN outcome = 'SUCCESS' THEN reward END) as avg_success_reward
                FROM runs
                {where_clause}
                """,
                params,
            ).fetchone()
            total_runs, successes, failures, avg_success_reward = stats

            if total_runs == 0:
                raise ValueError(f"No benchmark data found{' for ' + benchmark_id if benchmark_id else ''}")

            model_stats = conn.execute(
                f"""
                SELECT
                    json_extract(treatment, '$.model') as model,
                    COUNT(*) as runs,
                    COUNT(CASE WHEN outcome = 'SUCCESS' THEN 1 END) as successes,
                    AVG(CASE WHEN outcome = 'SUCCESS' THEN reward END) as avg_reward
                FROM runs
                {where_clause}
                GROUP BY model
                """,
                params,
            ).fetchall()

            quest_stats = conn.execute(
                f"""
                SELECT
                    quest_name,
                    COUNT(*) as runs,
                    COUNT(CASE WHEN outcome = 'SUCCESS' THEN 1 END) as successes
                FROM runs
                {where_clause}
                GROUP BY quest_name
                """,
                params,
            ).fetchall()

            treatment_stats = conn.execute(
                f"""
                SELECT
                    treatment_signature,
                    json_extract(treatment, '$.harness') as harness,
                    json_extract(treatment, '$.memory') as memory,
                    json_extract(treatment, '$.loop') as loop,
                    json_extract(treatment, '$.reasoning') as reasoning,
                    COUNT(*) as runs,
                    COUNT(CASE WHEN outcome = 'SUCCESS' THEN 1 END) as successes
                FROM runs
                {where_clause}
                GROUP BY treatment_signature
                """,
                params,
            ).fetchall()

            results = {
                "summary": {
                    "total_runs": total_runs,
                    "success_rate": (successes / total_runs * 100) if total_runs > 0 else 0,
                    "avg_success_reward": avg_success_reward or 0,
                    "outcomes": {"SUCCESS": successes, "FAILURE": failures},
                },
                "models": [
                    {
                        "name": model or "unknown",
                        "runs": runs,
                        "success_rate": (model_successes / runs * 100) if runs > 0 else 0,
                        "avg_reward": avg_reward or 0,
                    }
                    for model, runs, model_successes, avg_reward in model_stats
                ],
                "quests": [
                    {"name": quest, "runs": runs, "success_rate": (quest_successes / runs * 100) if runs > 0 else 0}
                    for quest, runs, quest_successes in quest_stats
                ],
                "treatments": [
                    {
                        "signature": signature,
                        "harness": harness,
                        "memory": memory,
                        "loop": loop,
                        "reasoning": reasoning,
                        "runs": runs,
                        "success_rate": (treatment_successes / runs * 100) if runs > 0 else 0,
                    }
                    for signature, harness, memory, loop, reasoning, runs, treatment_successes in treatment_stats
                ],
            }

            if benchmark_id:
                results["benchmark_id"] = benchmark_id
        finally:
            conn.close()

        # Create renderer and display results
        renderer = BenchmarkResultRenderer(debug=debug)
        renderer.render_benchmark_results(results, debug=debug)

        return results

    except ValueError:
        raise
    except Exception as e:
        log.exception(f"Error analyzing benchmark: {e}")
        raise ValueError(f"Error analyzing benchmark: {e}")
