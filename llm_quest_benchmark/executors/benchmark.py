"""Benchmark executor for running multiple quests with multiple agents"""

import json
import logging
import multiprocessing as mp
import queue
import sqlite3
import time
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from llm_quest_benchmark.agents.agent_factory import create_agent
from llm_quest_benchmark.core.logging import DEFAULT_DB_PATH
from llm_quest_benchmark.core.runner import run_quest_with_timeout
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.llm import tracing
from llm_quest_benchmark.schemas.config import BenchmarkConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    force=True,  # Override any existing logging configuration
)

# Reduce verbosity of other loggers
logging.getLogger("quest").setLevel(logging.WARNING)
logging.getLogger("llm_quest_benchmark").setLevel(logging.WARNING)
logging.getLogger("llm_quest_benchmark.executors.ts_bridge").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def _result_entry(
    quest: str,
    agent_config,
    attempt: int,
    outcome: str,
    reward: float = 0.0,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "quest": quest,
        "model": agent_config.model,
        "temperature": agent_config.temperature,
        "template": agent_config.action_template,
        "agent_id": agent_config.agent_id,
        "attempt": attempt,
        "outcome": outcome,
        "reward": reward,
        "error": error,
    }


def _mark_run_timeout(run_id: int | None, quest: str, agent_config, benchmark_id: str, timeout: int) -> None:
    """Record a parent-enforced timeout for a killed child process."""
    agent_config_json = json.dumps(agent_config.__dict__)
    end_time = datetime.utcnow()
    conn = sqlite3.connect(DEFAULT_DB_PATH)
    try:
        if run_id is not None:
            row = conn.execute("SELECT start_time FROM runs WHERE id = ?", (run_id,)).fetchone()
            run_duration = None
            if row and row[0]:
                try:
                    start_time = datetime.fromisoformat(str(row[0]))
                    run_duration = (end_time - start_time).total_seconds()
                except ValueError:
                    run_duration = None
            conn.execute(
                """
                UPDATE runs
                SET agent_id = ?, agent_config = ?, benchmark_id = ?, outcome = ?,
                    reward = ?, end_time = ?, run_duration = ?
                WHERE id = ?
                """,
                (
                    agent_config.agent_id,
                    agent_config_json,
                    benchmark_id,
                    QuestOutcome.TIMEOUT.name,
                    0.0,
                    end_time,
                    run_duration,
                    run_id,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO runs
                    (quest_file, quest_name, start_time, end_time, agent_id, agent_config,
                     outcome, reward, run_duration, benchmark_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    quest,
                    Path(quest).stem,
                    end_time,
                    end_time,
                    agent_config.agent_id,
                    agent_config_json,
                    QuestOutcome.TIMEOUT.name,
                    0.0,
                    0.0,
                    benchmark_id,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def _run_benchmark_task(task: dict[str, Any], result_queue) -> None:
    """Run one benchmark attempt in a child process."""
    agent_config = task["agent_config"]
    agent_config.benchmark_id = task["benchmark_id"]
    quest = task["quest"]
    attempt = task["attempt"]

    def callback(event: str, data: Any = None) -> None:
        if event == "run_record" and isinstance(data, dict):
            result_queue.put(
                {
                    "event": "run_record",
                    "run_index": task["run_index"],
                    "run_id": data.get("run_id"),
                }
            )

    try:
        agent = create_agent(
            model=agent_config.model,
            temperature=agent_config.temperature,
            system_template=agent_config.system_template,
            action_template=agent_config.action_template,
            skip_single=agent_config.skip_single,
            debug=agent_config.debug,
            memory_mode=agent_config.memory_mode,
            compaction_interval=agent_config.compaction_interval,
        )
        outcome = run_quest_with_timeout(
            quest,
            agent,
            timeout=10**9,
            agent_config=agent_config,
            debug=agent_config.debug,
            callbacks=[callback],
        )
        outcome_name = outcome.name if outcome else QuestOutcome.TIMEOUT.name
        result_queue.put(
            {
                "event": "done",
                "run_index": task["run_index"],
                "result": _result_entry(quest, agent_config, attempt, outcome_name),
            }
        )
    except Exception as exc:
        result_queue.put(
            {
                "event": "done",
                "run_index": task["run_index"],
                "result": _result_entry(quest, agent_config, attempt, QuestOutcome.ERROR.name, error=str(exc)),
            }
        )


def generate_benchmark_id(prefix: str = "benchmark") -> str:
    """Generate a unique benchmark id safe for parallel starts."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    return f"{prefix}_{stamp}_{suffix}"


def _emit_progress(progress_callback, payload: dict[str, Any]) -> None:
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


def get_quest_files(quest_paths: list[str], max_quests: int | None = None) -> list[Path]:
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


def _load_benchmark_runs_from_db(benchmark_id: str, db_path: str = DEFAULT_DB_PATH) -> list[dict[str, Any]]:
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


def _write_benchmark_artifacts(config: BenchmarkConfig, results: list[dict[str, Any]]) -> Path | None:
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
                "runs": agent.runs,
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
                "runs": agent.runs,
                "skip_single": agent.skip_single,
                "debug": agent.debug,
            }
            for agent in config.agents
        ],
    }
    with open(benchmark_dir / "benchmark_config.json", "w", encoding="utf-8") as f:
        json.dump(config_dump, f, indent=2, ensure_ascii=False)

    return benchmark_dir


def run_benchmark(config: BenchmarkConfig, progress_callback=None) -> list[dict[str, Any]]:
    """Run benchmark on a set of quests with multiple agents

    Args:
        config: Benchmark configuration
        progress_callback: Optional callback to report progress

    Returns:
        List of results for each quest/agent combination
    """
    # Generate a benchmark ID if not provided
    if not config.benchmark_id:
        config.benchmark_id = generate_benchmark_id("benchmark")

    logger.info(f"Running benchmark with ID: {config.benchmark_id}")

    # Expand quest paths into actual quest files
    quest_files = get_quest_files(config.quests, config.max_quests)
    logger.info(f"Found {len(quest_files)} quests to run")

    # Print summary of what will be run
    logger.info(f"Running {len(quest_files)} quests with {len(config.agents)} agents")
    logger.info(f"Agents: {', '.join(a.agent_id for a in config.agents)}")

    total_runs = len(quest_files) * sum(agent.runs for agent in config.agents)
    run_index = 0
    tasks = []

    for agent_config in config.agents:
        for quest_file in quest_files:
            for attempt in range(1, agent_config.runs + 1):
                run_index += 1
                quest_str = str(quest_file)
                quest_name = Path(quest_file).name
                task_agent_config = deepcopy(agent_config)
                task_agent_config.benchmark_id = config.benchmark_id
                tasks.append(
                    {
                        "run_index": run_index,
                        "total_runs": total_runs,
                        "quest": quest_str,
                        "quest_name": quest_name,
                        "agent_config": task_agent_config,
                        "attempt": attempt,
                        "benchmark_id": config.benchmark_id,
                    }
                )

                logger.info(
                    "Queued agent %s quest %s (attempt %s/%s)",
                    agent_config.agent_id,
                    quest_name,
                    attempt,
                    agent_config.runs,
                )

    max_workers = max(1, int(config.max_workers or 1))
    logger.info("Running %s benchmark attempts with max_workers=%s", total_runs, max_workers)

    # Collect results for each agent x quest combination.
    results_by_index: list[tuple[int, dict[str, Any]]] = []
    ctx = mp.get_context("spawn")
    running: dict[int, dict[str, Any]] = {}
    next_task = 0

    while next_task < len(tasks) or running:
        while next_task < len(tasks) and len(running) < max_workers:
            task = tasks[next_task]
            next_task += 1
            agent_config = task["agent_config"]
            task_queue = ctx.Queue()
            process = ctx.Process(target=_run_benchmark_task, args=(task, task_queue))
            process.start()
            running[task["run_index"]] = {
                "task": task,
                "queue": task_queue,
                "process": process,
                "started_at": time.monotonic(),
                "run_id": None,
            }
            logger.info(
                "Agent %s running quest %s (attempt %s/%s)",
                agent_config.agent_id,
                task["quest_name"],
                task["attempt"],
                agent_config.runs,
            )
            _emit_progress(
                progress_callback,
                {
                    "event": "pair_start",
                    "run_index": task["run_index"],
                    "total_runs": total_runs,
                    "quest": task["quest"],
                    "quest_name": task["quest_name"],
                    "agent_id": agent_config.agent_id,
                    "model": agent_config.model,
                    "attempt": task["attempt"],
                },
            )

        completed: list[int] = []
        for current_index, handle in list(running.items()):
            task = handle["task"]
            agent_config = task["agent_config"]
            process = handle["process"]
            task_queue = handle["queue"]
            while True:
                try:
                    message = task_queue.get_nowait()
                except queue.Empty:
                    break
                if message.get("event") == "run_record":
                    handle["run_id"] = message.get("run_id")
                elif message.get("event") == "done":
                    result = message["result"]
                    results_by_index.append((current_index, result))
                    completed.append(current_index)
                    process.join(timeout=1)
                    if process.is_alive():
                        process.terminate()
                        process.join(timeout=5)
                    _emit_progress(
                        progress_callback,
                        {
                            "event": "pair_done",
                            "run_index": current_index,
                            "total_runs": total_runs,
                            "quest": task["quest"],
                            "quest_name": task["quest_name"],
                            "agent_id": agent_config.agent_id,
                            "model": agent_config.model,
                            "attempt": task["attempt"],
                            "outcome": result["outcome"],
                            "error": result["error"],
                        },
                    )
                    break

            if current_index in completed:
                continue

            elapsed = time.monotonic() - handle["started_at"]
            if elapsed > max(config.quest_timeout, 1):
                logger.warning(
                    "Quest %s attempt %s timed out after %s seconds",
                    task["quest_name"],
                    task["attempt"],
                    config.quest_timeout,
                )
                process.terminate()
                process.join(timeout=5)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=1)
                _mark_run_timeout(
                    handle["run_id"], task["quest"], agent_config, config.benchmark_id, config.quest_timeout
                )
                result = _result_entry(
                    task["quest"],
                    agent_config,
                    task["attempt"],
                    QuestOutcome.TIMEOUT.name,
                    error=f"Timed out after {config.quest_timeout} seconds",
                )
                results_by_index.append((current_index, result))
                completed.append(current_index)
                _emit_progress(
                    progress_callback,
                    {
                        "event": "pair_done",
                        "run_index": current_index,
                        "total_runs": total_runs,
                        "quest": task["quest"],
                        "quest_name": task["quest_name"],
                        "agent_id": agent_config.agent_id,
                        "model": agent_config.model,
                        "attempt": task["attempt"],
                        "outcome": QuestOutcome.TIMEOUT.name,
                        "error": f"Timed out after {config.quest_timeout} seconds",
                    },
                )

            elif process.exitcode is not None and process.exitcode != 0:
                result = _result_entry(
                    task["quest"],
                    agent_config,
                    task["attempt"],
                    QuestOutcome.ERROR.name,
                    error=f"Worker exited with code {process.exitcode}",
                )
                results_by_index.append((current_index, result))
                completed.append(current_index)
                process.join()

        for current_index in completed:
            handle = running.pop(current_index, None)
            if handle:
                handle["queue"].close()

        if not completed:
            time.sleep(0.1)

    results = [result for _, result in sorted(results_by_index, key=lambda item: item[0])]

    artifact_dir = _write_benchmark_artifacts(config, results)
    if artifact_dir:
        logger.info("Benchmark artifacts saved to %s", artifact_dir)

    tracing.flush()
    return results


def calculate_summary_stats(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate detailed summary statistics for benchmark results

    Args:
        results (List[Dict[str, Any]]): List of benchmark results

    Returns:
        Dict[str, Any]: Summary statistics
    """
    summary = {
        "models": {},
        "total_runs": len(results),
        "total_success": len([r for r in results if r["outcome"] == QuestOutcome.SUCCESS.name]),
        "total_failures": len([r for r in results if r["outcome"] == QuestOutcome.FAILURE.name]),
        "total_errors": len([r for r in results if r["outcome"] == QuestOutcome.ERROR.name]),
        "total_timeouts": len([r for r in results if r["outcome"] == QuestOutcome.TIMEOUT.name]),
        "success_rate": 0,
        "error_rate": 0,
        "failure_rate": 0,
        "timeout_rate": 0,
    }

    # Calculate per-model statistics
    models = {r["model"] for r in results}
    for model in sorted(models):
        model_results = [r for r in results if r["model"] == model]
        success = len([r for r in model_results if r["outcome"] == QuestOutcome.SUCCESS.name])
        failed = len([r for r in model_results if r["outcome"] == QuestOutcome.FAILURE.name])
        error = len([r for r in model_results if r["outcome"] == QuestOutcome.ERROR.name])
        timeout = len([r for r in model_results if r["outcome"] == QuestOutcome.TIMEOUT.name])
        total = len(model_results)

        summary["models"][model] = {
            "total_runs": total,
            "success": success,
            "success_rate": success / total if total > 0 else 0,
            "failed": failed,
            "failure_rate": failed / total if total > 0 else 0,
            "errors": error,
            "error_rate": error / total if total > 0 else 0,
            "timeouts": timeout,
            "timeout_rate": timeout / total if total > 0 else 0,
        }

    # Calculate overall rates
    total = len(results)
    if total > 0:
        summary["success_rate"] = summary["total_success"] / total
        summary["failure_rate"] = summary["total_failures"] / total
        summary["error_rate"] = summary["total_errors"] / total
        summary["timeout_rate"] = summary["total_timeouts"] / total

    return summary


def print_summary(results: list[dict[str, Any]]) -> None:
    """Print benchmark results summary

    Args:
        results (List[Dict[str, Any]]): List of benchmark results
    """
    print("\nResults Summary:")
    print("=" * 80)

    # Calculate total steps (if available)
    steps_info_available = any("steps" in r for r in results)

    if steps_info_available:
        total_steps = sum(len(r.get("steps", [])) for r in results)
        steps_by_model = {}

    # Group by model
    models = {r["model"] for r in results}
    for model in sorted(models):
        model_results = [r for r in results if r["model"] == model]
        success = len([r for r in model_results if r["outcome"] == QuestOutcome.SUCCESS.name])
        failed = len([r for r in model_results if r["outcome"] == QuestOutcome.FAILURE.name])
        error = len([r for r in model_results if r["outcome"] == QuestOutcome.ERROR.name])
        timeout = len([r for r in model_results if r["outcome"] == QuestOutcome.TIMEOUT.name])
        total = len(model_results)

        # Calculate steps for this model (if available)
        if steps_info_available:
            model_steps = sum(len(r.get("steps", [])) for r in model_results)
            avg_steps = model_steps / total if total > 0 else 0
            steps_by_model[model] = (model_steps, avg_steps)

        print(f"\nModel: {model}")
        print(f"Total quests: {total}")
        print(f"Success: {success} ({success / total * 100:.1f}%)")
        print(f"Failed: {failed} ({failed / total * 100:.1f}%)")
        print(f"Error: {error} ({error / total * 100:.1f}%)")
        print(f"Timeout: {timeout} ({timeout / total * 100:.1f}%)")

        if steps_info_available:
            print(f"Total steps: {model_steps}")
            print(f"Average steps per quest: {avg_steps:.1f}")

    # Print overall steps summary (if available)
    if steps_info_available:
        print("\nOverall Steps Summary:")
        print("=" * 80)
        print(f"Total steps across all models: {total_steps}")
        print(f"Average steps per quest: {total_steps / len(results):.1f}")

    # List errors if any
    errors = [r for r in results if r.get("error")]
    if errors:
        print("\nErrors encountered:")
        print("=" * 80)
        for r in errors:
            print(f"{r['quest']} - {r['model']}: Error - {r['error']}")
