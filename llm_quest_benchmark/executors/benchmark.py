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

from llm_quest_benchmark.core.logging import default_db_path, ensure_v2_schema, verify_v2_schema
from llm_quest_benchmark.core.provenance import engine_revision, quest_checksum
from llm_quest_benchmark.core.runner import run_quest_with_timeout
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.harnesses.factory import create_harness
from llm_quest_benchmark.llm import tracing
from llm_quest_benchmark.schemas.config import BenchmarkConfig
from llm_quest_benchmark.schemas.records import SCHEMA_VERSION

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


def _agent_harness(agent_config) -> str:
    """Return the configured harness name."""
    return agent_config.harness


def _agent_model(agent_config) -> str:
    """Return the result model label for the executed harness."""
    harness = _agent_harness(agent_config)
    if harness == "human":
        return "human"
    if harness.startswith("random_choice"):
        return "random_policy"
    return agent_config.model


def _agent_id(agent_config) -> str:
    """Return the stable result identifier derived from the treatment."""
    return agent_config.agent_id


def _harnesses_by_model(results: list[dict[str, Any]]) -> dict[str, set[str]]:
    """Map each result model to the set of distinct harness values run under it."""
    by_model: dict[str, set[str]] = {}
    for r in results:
        by_model.setdefault(r.get("model", "unknown"), set()).add(r.get("harness") or "")
    return by_model


def _result_group_label(result: dict[str, Any], harnesses_by_model: dict[str, set[str]]) -> str:
    """Stable per-agent-variant label for grouping/reporting results.

    Distinguishes agents that share a model but run under different harnesses
    (e.g. a benchmark comparing several harnesses on the same model), so
    summary stats never silently collapse them into one row. Stays the bare
    model name -- preserving prior output exactly -- whenever that model only
    ran under one harness in these results, or the harness is one whose model
    label already encodes it (human, random_choice), or no harness is
    recorded at all.
    """
    model = result.get("model", "unknown")
    harness = result.get("harness") or ""
    if not harness or harness == "human" or harness.startswith("random_choice"):
        return model
    if len(harnesses_by_model.get(model, set())) <= 1:
        return model
    return f"{model} [{harness}]"


def _result_entry(
    quest: str,
    agent_config,
    attempt: int,
    outcome: str,
    reward: float = 0.0,
    error: str | None = None,
) -> dict[str, Any]:
    treatment = agent_config.treatment().to_dict()
    return {
        "quest": quest,
        "model": _agent_model(agent_config),
        "temperature": agent_config.temperature,
        "harness": _agent_harness(agent_config),
        "treatment": treatment,
        "treatment_signature": treatment["signature"],
        "agent_id": _agent_id(agent_config),
        "attempt": attempt,
        "outcome": outcome,
        "reward": reward,
        "error": error,
    }


def _mark_run_timeout(run_id: int | None, quest: str, agent_config, benchmark_id: str, timeout: int) -> None:
    """Record a parent-enforced timeout for a killed child process."""
    end_time = datetime.utcnow()
    treatment = agent_config.treatment().to_dict()
    conn = sqlite3.connect(default_db_path())
    try:
        ensure_v2_schema(conn)
        if run_id is not None:
            # The child already wrote complete run metadata before executing,
            # so the parent only records the terminal outcome.
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
                SET outcome = ?, reward = ?, end_time = ?, run_duration = ?
                WHERE id = ?
                """,
                (QuestOutcome.TIMEOUT.name, 0.0, end_time, run_duration, run_id),
            )
        else:
            # The child died before writing its run row; record the attempt with
            # the metadata the parent can prove.
            conn.execute(
                """
                INSERT INTO runs
                    (schema_version, quest_file, quest_name, quest_checksum, quest_language,
                     engine_revision, agent_id, treatment, treatment_signature, benchmark_id,
                     start_time, end_time, run_duration, outcome, reward)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    SCHEMA_VERSION,
                    quest,
                    Path(quest).stem,
                    quest_checksum(quest) if Path(quest).exists() else "unavailable",
                    "rus",
                    engine_revision(),
                    _agent_id(agent_config),
                    json.dumps(treatment, ensure_ascii=False),
                    treatment["signature"],
                    benchmark_id,
                    end_time,
                    end_time,
                    0.0,
                    QuestOutcome.TIMEOUT.name,
                    0.0,
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
    max_steps = task.get("max_steps")
    progress_manifest = task.get("progress_manifest")

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
        agent = create_harness(
            harness=_agent_harness(agent_config),
            model=agent_config.model,
            temperature=agent_config.temperature,
            skip_single=agent_config.skip_single,
            debug=agent_config.debug,
            compaction_interval=agent_config.compaction_interval,
            system_template=agent_config.system_template,
            restore_limit=agent_config.restore_limit,
            adaptive_stall_steps=agent_config.adaptive_stall_steps,
        )
        outcome = run_quest_with_timeout(
            quest,
            agent,
            timeout=10**9,
            agent_config=agent_config,
            debug=agent_config.debug,
            callbacks=[callback],
            max_steps=max_steps,
            progress_manifest=progress_manifest,
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


def _load_benchmark_runs_from_db(benchmark_id: str, db_path: str | None = None) -> list[dict[str, Any]]:
    """Load schema-v2 DB runs associated with a benchmark id.

    The database is resolved at call time, so workers and tests read the same
    database they wrote. A pre-v2 database raises with migration guidance rather
    than being probed column by column.
    """
    resolved = db_path or default_db_path()
    if not Path(resolved).exists():
        return []

    conn = sqlite3.connect(resolved)
    conn.row_factory = sqlite3.Row
    try:
        if not verify_v2_schema(conn):
            return []
        rows = conn.execute(
            """
            SELECT id, schema_version, quest_file, quest_name, quest_checksum, quest_language,
                   engine_revision, agent_id, treatment, treatment_signature, benchmark_id,
                   start_time, end_time, run_duration, outcome, reward, usage,
                   transcript_diagnostics, progress
            FROM runs
            WHERE benchmark_id = ?
            ORDER BY id
            """,
            (benchmark_id,),
        ).fetchall()
        runs = []
        for row in rows:
            run = dict(row)
            for key in ("treatment", "usage", "transcript_diagnostics", "progress"):
                if isinstance(run.get(key), str) and run[key]:
                    try:
                        run[key] = json.loads(run[key])
                    except json.JSONDecodeError:
                        run[key] = {}
            runs.append(run)
        return runs
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
                "harness": _agent_harness(agent),
                "treatment": agent.treatment().to_dict(),
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
        "max_steps": config.max_steps,
        "output_dir": config.output_dir,
        "name": config.name,
        "renderer": config.renderer,
        "benchmark_id": config.benchmark_id,
        "max_quests": config.max_quests,
        "max_workers": config.max_workers,
        "progress_manifest": config.progress_manifest,
        "agents": [
            {
                "model": agent.model,
                "system_template": agent.system_template,
                "harness": _agent_harness(agent),
                "temperature": agent.temperature,
                "runs": agent.runs,
                "skip_single": agent.skip_single,
                "debug": agent.debug,
                "compaction_interval": agent.compaction_interval,
                "restore_limit": agent.restore_limit,
                "adaptive_stall_steps": agent.adaptive_stall_steps,
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
                        "max_steps": config.max_steps,
                        "progress_manifest": config.progress_manifest,
                    }
                )

                logger.info(
                    "Queued agent %s quest %s (attempt %s/%s)",
                    _agent_id(agent_config),
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
                _agent_id(agent_config),
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
                    "agent_id": _agent_id(agent_config),
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
                            "agent_id": _agent_id(agent_config),
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
                        "agent_id": _agent_id(agent_config),
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

    # Calculate per-agent-variant statistics, keyed by model or, when distinct
    # harnesses share a model, by "model [harness]" so results never collapse.
    harnesses_by_model = _harnesses_by_model(results)
    groups = {_result_group_label(r, harnesses_by_model) for r in results}
    for group in sorted(groups):
        model_results = [r for r in results if _result_group_label(r, harnesses_by_model) == group]
        success = len([r for r in model_results if r["outcome"] == QuestOutcome.SUCCESS.name])
        failed = len([r for r in model_results if r["outcome"] == QuestOutcome.FAILURE.name])
        error = len([r for r in model_results if r["outcome"] == QuestOutcome.ERROR.name])
        timeout = len([r for r in model_results if r["outcome"] == QuestOutcome.TIMEOUT.name])
        total = len(model_results)

        summary["models"][group] = {
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

    # Group by agent variant (model, or "model [harness]" when a model is run
    # under more than one harness in these results).
    harnesses_by_model = _harnesses_by_model(results)
    groups = {_result_group_label(r, harnesses_by_model) for r in results}
    for group in sorted(groups):
        model_results = [r for r in results if _result_group_label(r, harnesses_by_model) == group]
        success = len([r for r in model_results if r["outcome"] == QuestOutcome.SUCCESS.name])
        failed = len([r for r in model_results if r["outcome"] == QuestOutcome.FAILURE.name])
        error = len([r for r in model_results if r["outcome"] == QuestOutcome.ERROR.name])
        timeout = len([r for r in model_results if r["outcome"] == QuestOutcome.TIMEOUT.name])
        total = len(model_results)

        label = "Agent" if "[" in group else "Model"
        print(f"\n{label}: {group}")
        print(f"Total quests: {total}")
        print(f"Success: {success} ({success / total * 100:.1f}%)")
        print(f"Failed: {failed} ({failed / total * 100:.1f}%)")
        print(f"Error: {error} ({error / total * 100:.1f}%)")
        print(f"Timeout: {timeout} ({timeout / total * 100:.1f}%)")

    # List errors if any
    errors = [r for r in results if r.get("error")]
    if errors:
        print("\nErrors encountered:")
        print("=" * 80)
        for r in errors:
            print(f"{r['quest']} - {_result_group_label(r, harnesses_by_model)}: Error - {r['error']}")
