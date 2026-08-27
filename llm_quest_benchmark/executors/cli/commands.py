"""CLI commands for llm-quest-benchmark"""

import json
import shutil
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Initialize quest registry early
from llm_quest_benchmark.core.quest_registry import get_registry

get_registry(reset_cache=True)
load_dotenv(dotenv_path=Path(__file__).resolve().parents[3] / ".env", override=False)

import typer

from llm_quest_benchmark.constants import (
    DEFAULT_MODEL,
    DEFAULT_QUEST,
    DEFAULT_TEMPERATURE,
    INFINITE_TIMEOUT,
    MODEL_CHOICES,
    SYSTEM_ROLE_TEMPLATE,
)
from llm_quest_benchmark.core.analyzer import analyze_benchmark, analyze_quest_run, load_transitions
from llm_quest_benchmark.core.benchmark_report import render_benchmark_report
from llm_quest_benchmark.core.leaderboard import generate_leaderboard
from llm_quest_benchmark.core.logging import LogManager, default_db_path
from llm_quest_benchmark.core.migration import migrate_records
from llm_quest_benchmark.core.replay import harness_config_from_record
from llm_quest_benchmark.core.runner import run_quest_with_timeout
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.executors.benchmark import (
    generate_benchmark_id,
    print_summary,
    run_benchmark,
)
from llm_quest_benchmark.harnesses.factory import create_harness
from llm_quest_benchmark.harnesses.specs import LLM_HARNESS_NAMES
from llm_quest_benchmark.llm import tracing
from llm_quest_benchmark.renderers.terminal import RichRenderer
from llm_quest_benchmark.schemas.config import BenchmarkConfig, HarnessConfig
from llm_quest_benchmark.schemas.records import RunRecord, load_run_record

# Initialize logging
log_manager = LogManager()
log = log_manager.get_logger()

app = typer.Typer(
    help="llm-quest: Command-line tools for LLM Quest Benchmark.",
    rich_markup_mode="rich",
)

HARNESS_CHOICES = list(LLM_HARNESS_NAMES)


def version_callback(value: bool):
    if value:
        typer.echo("llm-quest version 0.1.0")
        raise typer.Exit()


def _parse_run_dir_id(path: Path) -> int:
    """Parse run_<id> directory names for sorting."""
    try:
        return int(path.name.split("_", 1)[1])
    except (IndexError, ValueError):
        return -1


def _load_run_summary(path: Path) -> RunRecord:
    """Load a schema-v2 run record; legacy files are rejected with guidance."""
    return load_run_record(str(path))


def _count_quest_collections(quests_root: Path) -> list[dict[str, Any]]:
    """Count quest files in each normalized collection directory."""
    if not quests_root.exists():
        return []

    collections = []
    for collection_dir in sorted(path for path in quests_root.iterdir() if path.is_dir()):
        count = sum(
            1
            for quest_file in collection_dir.rglob("*")
            if quest_file.is_file() and quest_file.suffix.lower() in {".qm", ".qmm"}
        )
        collections.append(
            {
                "collection": collection_dir.name,
                "language": "EN" if collection_dir.name.endswith("_eng") else "RU",
                "count": count,
            }
        )
    return collections


def _summarize_quest_collections(collections: list[dict[str, Any]]) -> dict[str, int]:
    """Aggregate quest counts by language."""
    en_total = sum(item["count"] for item in collections if item["language"] == "EN")
    ru_total = sum(item["count"] for item in collections if item["language"] == "RU")
    return {
        "EN": en_total,
        "RU": ru_total,
        "TOTAL": en_total + ru_total,
    }


def _choices_map(choices: list[dict[str, str]]) -> dict[str, str]:
    """Index the choices of a snapshot for display."""
    return {str(index): choice.get("text", "") for index, choice in enumerate(choices, start=1)}


def _selected_label(transition: Any, choices_map: dict[str, str]) -> str:
    """Render the executed action of a transition for display."""
    action = transition.action
    if action.is_restore:
        return f"restore checkpoint {action.checkpoint_index}"
    index = str(action.choice_index) if action.choice_index is not None else ""
    if index and index in choices_map:
        return f"{index}:{choices_map[index]}"
    return "none"


def _handle_quest_outcome(outcome: QuestOutcome, log_prefix: str) -> None:
    """Handle quest outcome and exit appropriately.

    Args:
        outcome: The quest outcome to handle
        log_prefix: Prefix for the log message (e.g. "Quest run" or "Quest play")
    """
    if outcome is None:
        log.error(f"{log_prefix} timed out")
        raise typer.Exit(code=1)

    log.info(f"{log_prefix} completed with outcome: {outcome}")
    if outcome.is_error:
        log.error("Quest encountered an error")
    raise typer.Exit(code=outcome.exit_code)


@app.command("analyze-run")
def analyze_run(
    run_summary: Path | None = typer.Option(None, help="Path to run_summary.json."),
    agent: str | None = typer.Option(None, help="Agent results folder name (e.g. llm_gpt-5-mini)."),
    quest: str | None = typer.Option(None, help="Quest results folder name (e.g. Diehard)."),
    max_steps: int = typer.Option(25, help="Max decision steps to print."),
):
    """Analyze one run summary and print decision-level diagnostics."""
    try:
        summary_path = run_summary
        if summary_path is None:
            if not agent or not quest:
                typer.echo(
                    "Provide --run-summary or both --agent and --quest to auto-locate latest run.",
                    err=True,
                )
                raise typer.Exit(code=1)

            run_root = Path("results") / agent / quest
            if not run_root.exists():
                typer.echo(f"Run directory not found: {run_root}", err=True)
                raise typer.Exit(code=1)

            run_dirs = sorted(
                [p for p in run_root.iterdir() if p.is_dir() and p.name.startswith("run_")],
                key=_parse_run_dir_id,
            )
            if not run_dirs:
                typer.echo(f"No run_* directories found under {run_root}", err=True)
                raise typer.Exit(code=1)
            summary_path = run_dirs[-1] / "run_summary.json"

        if not summary_path.exists():
            typer.echo(f"run_summary not found: {summary_path}", err=True)
            raise typer.Exit(code=1)

        record = _load_run_summary(summary_path)
        outcome = record.outcome or "UNKNOWN"

        typer.echo(f"Run: {summary_path}")
        typer.echo(f"Quest: {record.quest_name}")
        typer.echo(f"Agent: {record.agent_id}")
        typer.echo(f"Treatment: {record.treatment_signature}")
        typer.echo(f"Outcome: {outcome}")
        typer.echo(f"Progress: {record.progress.current:.1f}% of {record.progress.maximum:.1f}%")
        typer.echo(f"Total Steps: {len(record.transitions)}")
        if record.lineage:
            typer.echo(f"Resumed from: {record.lineage.source_path} (run {record.lineage.source_run_id})")

        decision_rows = []
        for transition in record.transitions:
            choices_map = _choices_map(transition.before.choices)
            if len(choices_map) <= 1 and not transition.action.is_restore:
                continue
            response = transition.response
            decision_rows.append(
                {
                    "step": transition.index,
                    "observation": transition.before.agent_observation(),
                    "choices": choices_map,
                    "selected": _selected_label(transition, choices_map),
                    "analysis": response.analysis if response else None,
                    "reasoning": response.reasoning if response else None,
                    "is_default": bool(response.is_default) if response else False,
                    "reasoning_mode": transition.reasoning_mode,
                    "progress": transition.progress.current,
                }
            )

        typer.echo(f"Decision Steps: {len(decision_rows)}")
        if not decision_rows:
            return

        typer.echo("\nDecision Trace:")
        for row in decision_rows[:max_steps]:
            mode = f" mode={row['reasoning_mode']}" if row["reasoning_mode"] else ""
            typer.echo(
                f"- step {row['step']}: selected [{row['selected']}] "
                f"default={row['is_default']} progress={row['progress']:.1f}%{mode}"
            )
            if row["reasoning"]:
                typer.echo(f"  reasoning: {row['reasoning']}")
            if row["analysis"]:
                typer.echo(f"  analysis: {row['analysis']}")

        if outcome != QuestOutcome.SUCCESS.name:
            last = decision_rows[-1]
            typer.echo("\nFailure Focus:")
            typer.echo(f"- last decision step: {last['step']}")
            typer.echo(f"- observation: {(last['observation'] or '')[:280]}")
            typer.echo("- available choices:")
            for idx, text in last["choices"].items():
                typer.echo(f"  {idx}: {text}")
            typer.echo(f"- selected: {last['selected']}")

    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error analyzing run summary: {str(e)}", err=True)
        raise typer.Exit(code=2)


@app.command("benchmark-report")
def benchmark_report(
    benchmark_id: list[str] | None = typer.Option(
        None,
        "--benchmark-id",
        help="Benchmark ID(s) to include. Repeat flag to compare multiple IDs.",
    ),
    output: Path | None = typer.Option(
        None,
        help="Optional output markdown path. If omitted, prints to stdout.",
    ),
    output_dir: Path = typer.Option(
        Path("results/benchmarks"),
        help="Directory containing benchmark artifacts.",
    ),
):
    """Render markdown report from benchmark artifacts and run summaries."""
    try:
        report_md, selected_ids = render_benchmark_report(
            benchmark_ids=benchmark_id,
            output_dir=str(output_dir),
        )
        if output is None:
            typer.echo(report_md)
            return

        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report_md, encoding="utf-8")
        typer.echo(f"Benchmark report written to {output} for: {', '.join(selected_ids)}")
    except Exception as e:
        typer.echo(f"Error creating benchmark report: {str(e)}", err=True)
        raise typer.Exit(code=2)


@app.command("leaderboard")
def leaderboard(
    benchmark_dir: list[str] | None = typer.Option(
        None,
        "--benchmark-dir",
        help="Benchmark directory, parent directory, or glob pattern. Repeat to combine multiple inputs.",
    ),
    output: Path = typer.Option(
        Path("site/leaderboard.json"),
        help="Output path for leaderboard JSON.",
    ),
):
    """Generate leaderboard JSON from benchmark artifacts."""
    try:
        inputs = benchmark_dir or ["results/benchmarks"]
        generate_leaderboard(benchmark_dirs=inputs, output_path=str(output))
        typer.echo(f"Leaderboard written to {output}")
    except Exception as e:
        typer.echo(f"Error creating leaderboard: {str(e)}", err=True)
        raise typer.Exit(code=2)


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
):
    """
    llm-quest: Command-line tools for LLM Quest Benchmark.

    Run and analyze LLM agent performance on Space Rangers text quests.
    """
    pass


@app.command()
def run(
    quest: Path = typer.Option(DEFAULT_QUEST, help="Path to the QM quest file."),
    model: str = typer.Option(DEFAULT_MODEL, help=f"Model for the LLM agent (choices: {', '.join(MODEL_CHOICES)})."),
    temperature: float = typer.Option(DEFAULT_TEMPERATURE, help="Temperature for LLM sampling"),
    system_template: str = typer.Option(SYSTEM_ROLE_TEMPLATE, help="Template to use for system instructions."),
    harness: str = typer.Option(
        "reasoning_recent",
        "--harness",
        help="Harness to use for quest decisions.",
    ),
    compaction_interval: int = typer.Option(50, help="Advanced override for compaction interval."),
    restore_limit: int | None = typer.Option(None, help="Restore budget; valid only for the backtracking harness."),
    adaptive_stall_steps: int | None = typer.Option(
        None, help="Stall trigger; valid only for the adaptive_reasoning harness."
    ),
    max_steps: int | None = typer.Option(None, help="Stop after this many steps and record a resumable TRUNCATED run."),
    progress_manifest: Path | None = typer.Option(None, help="Curated YAML progress manifest for this quest."),
    resume_from: Path | None = typer.Option(
        None, help="Resume a schema-v2 run_summary.json; quest and treatment come from the record."
    ),
    timeout: int = typer.Option(60, help="Timeout in seconds for run (0 for no timeout)."),
    skip: bool = typer.Option(True, help="Auto-select single choices without asking agent."),
    debug: bool = typer.Option(False, help="Enable debug logging and output, remove terminal UI."),
):
    """Run a quest with an LLM agent.

    This command runs a Space Rangers quest using an LLM agent. The agent will attempt to complete
    the quest by making decisions based on the quest text and available choices.

    Example:
        llm-quest run --quest quests/boat.qm --model sonnet --debug
        llm-quest run --quest quests/Boat.qm --max-steps 5
        llm-quest run --resume-from results/<agent>/Boat/run_12/run_summary.json
    """
    try:
        log_manager.setup(debug)

        resume_record = None
        if resume_from is not None:
            resume_record = load_run_record(str(resume_from))
            if not resume_record.is_resumable:
                typer.echo(
                    f"Run {resume_from} is not resumable "
                    f"(outcome={resume_record.outcome}); only verified TRUNCATED runs can continue.",
                    err=True,
                )
                raise typer.Exit(code=1)
            # Quest and treatment come from the record, not from the CLI flags.
            agent_config = harness_config_from_record(resume_record)
            quest = Path(resume_record.quest_file)
            agent_config.skip_single = skip
            agent_config.debug = debug
            log.warning(f"Resuming run {resume_record.run_id} from {resume_from}")
        else:
            agent_config = HarnessConfig(
                model=model,
                system_template=system_template,
                harness=harness,
                temperature=temperature,
                skip_single=skip,
                debug=debug,
                compaction_interval=compaction_interval,
                restore_limit=restore_limit,
                adaptive_stall_steps=adaptive_stall_steps,
            )

        # Create agent
        agent = create_harness(
            harness=agent_config.harness,
            model=agent_config.model,
            system_template=agent_config.system_template,
            temperature=agent_config.temperature,
            skip_single=agent_config.skip_single,
            debug=agent_config.debug,
            compaction_interval=agent_config.compaction_interval,
            restore_limit=agent_config.restore_limit,
            adaptive_stall_steps=agent_config.adaptive_stall_steps,
        )

        log.warning(f"Starting quest run with agent {str(agent)}")
        log.debug(f"Quest file: {quest}")
        log.debug(f"Timeout: {timeout}s")

        # Create callbacks based on debug mode
        callbacks = []
        if not debug:
            # Create a rich renderer for terminal UI when not in debug mode
            renderer = RichRenderer()

            # Define callbacks that use the renderer
            def title_callback(event, data):
                if event == "title":
                    renderer.render_title()

            def game_state_callback(event, data):
                if event == "game_state":
                    renderer.render_game_state(data)

            def progress_callback(event, data):
                if event == "progress":
                    # Optional: Show progress information
                    pass

            def error_callback(event, data):
                if event == "error":
                    renderer.render_error(data)

            def close_callback(event, data):
                if event == "close":
                    renderer.close()

            callbacks = [title_callback, game_state_callback, progress_callback, error_callback, close_callback]

        timeout = timeout if timeout > 0 else 10**9
        result = run_quest_with_timeout(
            quest_path=str(quest),
            agent=agent,
            debug=debug,
            timeout=timeout,
            agent_config=agent_config,
            callbacks=callbacks,
            max_steps=max_steps,
            progress_manifest=str(progress_manifest) if progress_manifest else None,
            resume_record=resume_record,
            resume_path=str(resume_from) if resume_from else None,
        )
        _handle_quest_outcome(result, "Quest run")

    except typer.Exit:
        raise  # Re-raise typer.Exit without logging
    except Exception as e:
        log.exception(f"Error during quest run: {e}")
        raise typer.Exit(code=2)
    finally:
        tracing.flush()


@app.command()
def play(
    quest: Path = typer.Option(DEFAULT_QUEST, help="Path to the QM quest file."),
    skip: bool = typer.Option(False, help="Automatically select screens with only one available option."),
    debug: bool = typer.Option(False, help="Enable debug logging and output."),
):
    """Play a Space Rangers quest interactively.

    This command allows you to play a quest in interactive mode through the terminal.
    Choices are presented and you can select them using numbers.

    Example:
        llm-quest play --quest quests/boat.qm --skip
    """
    try:
        log_manager.setup(debug)
        log.info("Starting interactive quest play")
        log.debug(f"Quest file: {quest}")

        # Create interactive player
        player = create_harness(harness="human", skip_single=skip, debug=debug)

        # Run quest in interactive mode
        result = run_quest_with_timeout(quest_path=str(quest), agent=player, timeout=INFINITE_TIMEOUT, debug=debug)
        _handle_quest_outcome(result, "Quest play")

    except typer.Exit:
        raise  # Re-raise typer.Exit without logging
    except Exception as e:
        log.exception(f"Error during interactive play: {e}")
        raise typer.Exit(code=2)


@app.command("download-quests")
def download_quests() -> None:
    """Download the upstream quest corpus and print per-collection counts.

    TODO: rewrite download_quests.sh logic in Python to avoid subprocess shell call.
    """
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "download_quests.sh"
    quests_root = repo_root / "quests"

    if not script_path.exists():
        typer.echo(f"Quest download script not found: {script_path}", err=True)
        raise typer.Exit(code=1)

    try:
        subprocess.run(["bash", str(script_path)], cwd=repo_root, check=True)
    except subprocess.CalledProcessError as exc:
        typer.echo(f"Quest download failed with exit code {exc.returncode}", err=True)
        raise typer.Exit(code=exc.returncode) from exc

    get_registry(reset_cache=True)

    collections = _count_quest_collections(quests_root)
    totals = _summarize_quest_collections(collections)

    typer.echo("Quest counts by collection:")
    for collection in collections:
        typer.echo(f"- {collection['collection']} ({collection['language']}): {collection['count']} .qm/.qmm files")

    typer.echo(f"Totals: EN={totals['EN']} RU={totals['RU']} TOTAL={totals['TOTAL']}")

    english_collection = next(
        (item for item in collections if item["collection"] == "sr_2_1_2121_eng"),
        None,
    )
    if english_collection and english_collection["count"] < 35:
        typer.echo(
            "Blocker: sr_2_1_2121_eng has fewer than 35 English quests.",
            err=True,
        )


@app.command()
def analyze(
    quest: str | None = typer.Option(None, help="Name of the quest to analyze (e.g. 'boat.qm')."),
    benchmark: str | None = typer.Option(None, help="Benchmark ID to analyze (e.g. 'CLI_benchmark_20260101_...')."),
    run_id: int | None = typer.Option(None, help="Specific run ID to analyze in detail."),
    last: bool = typer.Option(False, help="Analyze the most recent quest run."),
    db: Path | None = typer.Option(
        None, help="Path to SQLite database (defaults to $LLM_QUEST_DB_PATH, else metrics.db)."
    ),
    export: Path | None = typer.Option(None, help="Export results to JSON file."),
    format: str = typer.Option("summary", help="Output format (summary, detail, or compact)."),
    debug: bool = typer.Option(False, help="Enable debug logging and output."),
):
    """Analyze metrics from quest runs or benchmark results.

    This command analyzes metrics from the SQLite database, showing summary statistics and detailed analysis.
    You can either analyze a specific quest (using --quest), a benchmark (using --benchmark),
    a specific run by ID (using --run-id), or the most recent run (using --last).

    Example:
        llm-quest analyze --last                 # Analyze the most recent quest run
        llm-quest analyze --run-id 123           # Analyze specific run by ID
        llm-quest analyze --quest boat.qm        # Analyze all runs of specific quest
        llm-quest analyze --benchmark baseline   # Analyze benchmark results
        llm-quest analyze --quest boat.qm --export results.json  # Export to JSON
    """
    try:
        log_manager.setup(debug)

        # Validate input parameters
        options_count = sum(1 for opt in [quest, benchmark, run_id, last] if opt)
        if options_count == 0:
            typer.echo("Must specify one of: --quest, --benchmark, --run-id, or --last", err=True)
            raise typer.Exit(code=1)
        if options_count > 1:
            typer.echo("Please choose only one option from: --quest, --benchmark, --run-id, or --last", err=True)
            raise typer.Exit(code=1)

        # Validate database exists
        db = db or Path(default_db_path())
        if not db.exists():
            typer.echo(f"Database not found: {db}", err=True)
            raise typer.Exit(code=1)

        # Connect to database
        conn = sqlite3.connect(db)
        cursor = conn.cursor()

        # Handle --last option (find most recent run)
        if last:
            cursor.execute("SELECT id, quest_name FROM runs ORDER BY start_time DESC LIMIT 1")
            result = cursor.fetchone()
            if not result:
                typer.echo("No quest runs found in database", err=True)
                raise typer.Exit(code=1)
            run_id = result[0]
            typer.echo(f"Analyzing most recent run (ID: {run_id}, Quest: {result[1]})")

        # Analyze specific run by ID
        if run_id:
            cursor.execute(
                """
                SELECT id, quest_name, start_time, end_time, agent_id, treatment, treatment_signature,
                       outcome, reward, run_duration, usage, transcript_diagnostics, progress
                FROM runs
                WHERE id = ?
                """,
                (run_id,),
            )

            run = cursor.fetchone()
            if not run:
                typer.echo(f"Run ID {run_id} not found", err=True)
                raise typer.Exit(code=1)

            (
                run_id,
                quest_name,
                start_time,
                end_time,
                agent_id,
                treatment_json,
                treatment_signature,
                outcome,
                reward,
                run_duration,
                usage_json,
                diagnostics_json,
                progress_json,
            ) = run

            treatment = json.loads(treatment_json) if treatment_json else {}
            transitions = load_transitions(conn, run_id)
            decision_points = sum(1 for t in transitions if len(t.before.choices) > 1)

            # Exported in canonical domains, matching run_summary.json.
            run_data = {
                "schema_version": 2,
                "run": {
                    "id": run_id,
                    "agent_id": agent_id,
                    "started_at": start_time,
                    "ended_at": end_time,
                    "duration": run_duration,
                },
                "quest": {"name": quest_name},
                "treatment": treatment,
                "terminal": {"outcome": outcome, "reward": reward},
                "usage": json.loads(usage_json) if usage_json else {},
                "progress": json.loads(progress_json) if progress_json else {},
                "transcript_diagnostics": json.loads(diagnostics_json) if diagnostics_json else {},
                "transitions": [t.to_dict() for t in transitions],
            }

            # Export if requested
            if export:
                with open(export, "w") as f:
                    json.dump(run_data, f, indent=2, ensure_ascii=False)
                typer.echo(f"Results exported to {export}")

            duration_text = f"{run_duration:.2f}" if run_duration is not None else "n/a"
            progress_text = f"{run_data['progress'].get('current', 0.0):.1f}%"

            # Print human-readable summary based on format
            if format == "summary":
                typer.echo("\n📊 Run Summary")
                typer.echo("==============")
                typer.echo(f"Run ID: {run_id}")
                typer.echo(f"Quest: {quest_name}")
                typer.echo(f"Agent: {agent_id}")
                typer.echo(f"Treatment: {treatment_signature}")
                typer.echo(f"Start Time: {start_time}")
                typer.echo(f"Duration: {duration_text} seconds")
                typer.echo(f"Outcome: {outcome}")
                typer.echo(f"Reward: {reward}")
                typer.echo(f"Progress: {progress_text}")
                typer.echo(f"Total Transitions: {len(transitions)}")
                typer.echo(f"Decision Points: {decision_points}")

            elif format == "detail":
                typer.echo("\n📊 Run Details")
                typer.echo("=============")
                typer.echo(f"Run ID: {run_id}")
                typer.echo(f"Quest: {quest_name}")
                typer.echo(f"Agent: {agent_id}")
                typer.echo(f"Start Time: {start_time}")
                typer.echo(f"End Time: {end_time}")
                typer.echo(f"Duration: {duration_text} seconds")
                typer.echo(f"Outcome: {outcome}")
                typer.echo(f"Reward: {reward}")
                typer.echo(f"Progress: {progress_text}")

                typer.echo("\nTreatment:")
                for key, value in sorted(treatment.items()):
                    typer.echo(f"  {key}: {value}")

                typer.echo(f"\nTransitions ({len(transitions)} total):")
                for transition in transitions:
                    typer.echo(f"\n🔹 Transition {transition.index}:")
                    typer.echo(f"  Location: {transition.before.location_id}")

                    obs = transition.before.observation
                    if len(obs) > 100:
                        obs = obs[:97] + "..."
                    typer.echo(f"  Observation: {obs}")

                    if transition.before.choices:
                        typer.echo(f"  Choices ({len(transition.before.choices)}):")
                        for j, choice in enumerate(transition.before.choices, 1):
                            choice_text = choice["text"]
                            if len(choice_text) > 50:
                                choice_text = choice_text[:47] + "..."
                            typer.echo(f"    {j}. {choice_text}")

                    typer.echo(f"  Action: {_selected_label(transition, _choices_map(transition.before.choices))}")

                    if debug and transition.response and transition.response.reasoning:
                        typer.echo(f"  Reasoning: {transition.response.reasoning}")

            elif format == "compact":
                typer.echo(
                    f"Run {run_id}: {quest_name} - {outcome} (Reward: {reward}) - "
                    f"Transitions: {len(transitions)} - Agent: {agent_id}"
                )

        # Analyze quest runs
        elif quest:
            results = analyze_quest_run(quest, db, debug)

            # Export if requested
            if export:
                with open(export, "w") as f:
                    json.dump(results, f, indent=2)
                typer.echo(f"Results exported to {export}")

            # Print human-readable summary based on format
            if format == "summary" or format == "compact":
                typer.echo("\n📊 Quest Run Summary")
                typer.echo("===================")
                typer.echo(f"Quest: {results['quest_name']}")
                typer.echo(f"Total Runs: {results['total_runs']}")

                # Success rate calculation
                success_count = results["outcomes"].get("SUCCESS", 0)
                success_rate = (success_count / results["total_runs"] * 100) if results["total_runs"] > 0 else 0
                typer.echo(f"Success Rate: {success_rate:.1f}%")

                # Outcome breakdown
                typer.echo("\nOutcomes:")
                for outcome, count in results["outcomes"].items():
                    typer.echo(f"  {outcome}: {count} ({count / results['total_runs'] * 100:.1f}%)")

                # Agent performance
                agents = {}
                for run in results["runs"]:
                    agent = run.get("model", "unknown")
                    if agent not in agents:
                        agents[agent] = {"total": 0, "success": 0}

                    agents[agent]["total"] += 1
                    if run.get("outcome") == "SUCCESS":
                        agents[agent]["success"] += 1

                if agents and format == "summary":
                    typer.echo("\nAgent Performance:")
                    for agent, stats in agents.items():
                        success_rate = (stats["success"] / stats["total"] * 100) if stats["total"] > 0 else 0
                        typer.echo(f"  {agent}: {stats['success']}/{stats['total']} ({success_rate:.1f}%)")

            if format == "detail":
                # Print detailed run information
                typer.echo("\n📊 Run Details")
                typer.echo("=============")

                for i, run in enumerate(results["runs"], 1):
                    typer.echo(f"\n🔸 Run {i} (ID: {run.get('id', 'unknown')}):")
                    typer.echo(f"  Start Time: {run['start_time']}")
                    typer.echo(f"  Agent: {run.get('model', 'unknown')}")
                    typer.echo(f"  Harness: {run.get('harness', 'unknown')}")
                    typer.echo(f"  Outcome: {run['outcome']}")
                    typer.echo(f"  Reward: {run['reward']}")

                    # Only show transitions in debug mode to avoid output overload
                    if debug and run.get("transitions"):
                        typer.echo(f"\n  Transitions ({len(run['transitions'])} total):")
                        for transition in run["transitions"]:
                            action = transition["action"]
                            label = (
                                f"restore {action['checkpoint_index']}"
                                if action["kind"] == "restore"
                                else f"choose {action['choice_index']}"
                            )
                            typer.echo(f"    Transition {transition['index']}: {label}")

        # Analyze benchmark results
        else:
            results = analyze_benchmark(db, benchmark, debug)

            # Export if requested
            if export and results:
                with open(export, "w") as f:
                    json.dump(results, f, indent=2)
                typer.echo(f"Results exported to {export}")

    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        log.exception(f"Error during analysis: {e}")
        raise typer.Exit(code=1)

    finally:
        if "conn" in locals():
            conn.close()


@app.command("migrate-records")
def migrate_records_command(
    source: Path = typer.Option(..., "--source", help="Legacy run_summary.json, results tree, or SQLite database."),
    output: Path = typer.Option(..., "--output", help="Destination for the schema-v2 records."),
):
    """Convert legacy records into schema v2.

    This is the only legacy reader in the project. Migration never invents a
    missing action, timestamp, parameter state, engine saving, or post-state;
    unknowable fields are marked unavailable and block resume.

    Example:
        llm-quest migrate-records --source results/ --output results_v2/
        llm-quest migrate-records --source metrics.db --output metrics_v2.db
    """
    try:
        report = migrate_records(source, output)
        typer.echo(f"Migrated {report.runs_migrated} runs ({report.kind}) to {report.output}")
        typer.echo(f"Transitions migrated: {report.transitions_migrated}")
        typer.echo(f"Resumable runs: {report.resumable_runs}")
        for skipped in report.skipped:
            typer.echo(f"Skipped {skipped}", err=True)
    except (FileNotFoundError, ValueError) as e:
        typer.echo(f"Migration failed: {e}", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        log.exception(f"Error during migration: {e}")
        raise typer.Exit(code=2)


@app.command()
def cleanup(
    db_path: Path | None = typer.Option(
        None, help="Path to SQLite database file (defaults to $LLM_QUEST_DB_PATH, else metrics.db)."
    ),
    older_than: str | None = typer.Option(None, help="ISO date (YYYY-MM-DD) to delete records older than this date."),
    all: bool = typer.Option(False, help="Delete all records from the database."),
    truncate_json: bool = typer.Option(False, help="Also remove JSON result files from results/ directory."),
    backup: bool = typer.Option(True, help="Create a backup before modifying the database."),
):
    """Clean up metrics database and optionally JSON result files.

    This command provides options to clean up the metrics database by deleting records older than
    a specific date or by removing all records. It can also optionally remove JSON result files.

    Example:
        llm-quest cleanup --older-than 2023-01-01  # Delete records older than 2023-01-01
        llm-quest cleanup --all                    # Delete all database records
        llm-quest cleanup --truncate-json          # Also delete JSON result files
    """
    try:
        # Check if database exists
        db_path = db_path or Path(default_db_path())
        if not db_path.exists():
            typer.echo(f"Database not found: {db_path}", err=True)
            raise typer.Exit(code=1)

        # Create backup if requested
        if backup:
            backup_path = f"{db_path}.bak"
            typer.echo(f"Creating backup at {backup_path}")
            shutil.copy2(db_path, backup_path)

        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get initial counts
        cursor.execute("SELECT count(*) FROM runs")
        initial_runs = cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM transitions")
        initial_transitions = cursor.fetchone()[0]

        deleted_runs = 0
        deleted_transitions = 0

        # Delete by date
        if older_than:
            try:
                # Parse date string
                cutoff_date = datetime.fromisoformat(older_than)
                typer.echo(f"Deleting records older than {cutoff_date.strftime('%Y-%m-%d')}")

                # Get run IDs to delete
                cursor.execute("SELECT id FROM runs WHERE start_time < ?", (cutoff_date.isoformat(),))
                run_ids = [row[0] for row in cursor.fetchall()]

                # Delete transitions first
                if run_ids:
                    placeholders = ",".join("?" for _ in run_ids)
                    cursor.execute(f"DELETE FROM transitions WHERE run_id IN ({placeholders})", run_ids)
                    deleted_transitions = cursor.rowcount

                    # Then delete runs
                    cursor.execute(f"DELETE FROM runs WHERE id IN ({placeholders})", run_ids)
                    deleted_runs = cursor.rowcount

                conn.commit()
                typer.echo(f"Deleted {deleted_runs} runs and {deleted_transitions} transitions")

            except ValueError:
                typer.echo(f"Invalid date format: {older_than}. Use YYYY-MM-DD format.", err=True)
                raise typer.Exit(code=1)

        # Delete all records
        elif all:
            typer.echo("Deleting all records from database")

            # Delete transitions first (due to foreign key constraints)
            cursor.execute("DELETE FROM transitions")
            deleted_transitions = cursor.rowcount

            # Then delete runs
            cursor.execute("DELETE FROM runs")
            deleted_runs = cursor.rowcount

            conn.commit()
            typer.echo(f"Deleted {deleted_runs} runs and {deleted_transitions} transitions")

        else:
            typer.echo("No action specified. Use --older-than or --all to specify what to delete.")

        # Remove JSON files if requested
        if truncate_json:
            results_dir = Path("results")
            if results_dir.exists() and results_dir.is_dir():
                typer.echo("Removing JSON result files")
                # Count files before deletion
                file_count = sum(1 for _ in results_dir.glob("**/*.json"))
                # Remove all JSON files
                for json_file in results_dir.glob("**/*.json"):
                    json_file.unlink()
                typer.echo(f"Removed {file_count} JSON files")

                # Also remove empty directories
                for agent_dir in results_dir.iterdir():
                    if agent_dir.is_dir():
                        # Check if directory is empty after removing JSONs
                        if not any(agent_dir.iterdir()):
                            agent_dir.rmdir()
                            typer.echo(f"Removed empty directory: {agent_dir}")
            else:
                typer.echo("Results directory not found, no JSON files to remove")

        # Print summary of changes
        cursor.execute("SELECT count(*) FROM runs")
        final_runs = cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM transitions")
        final_transitions = cursor.fetchone()[0]

        typer.echo("\nSummary:")
        typer.echo(f"Runs: {initial_runs} -> {final_runs} ({initial_runs - final_runs} removed)")
        typer.echo(
            f"Transitions: {initial_transitions} -> {final_transitions} "
            f"({initial_transitions - final_transitions} removed)"
        )

    except Exception as e:
        typer.echo(f"Error during cleanup: {str(e)}", err=True)
        raise typer.Exit(code=1)
    finally:
        if "conn" in locals():
            conn.close()


@app.command()
def benchmark(
    config: Path = typer.Option(..., help="Path to benchmark configuration YAML file."),
    debug: bool = typer.Option(False, help="Enable debug logging and output."),
):
    """Run benchmark evaluation on a set of quests.

    This command runs benchmark evaluation using a YAML configuration file that specifies:
    - quests: list of quest files or directories to test
    - agents: list of harnesses with their model, harness, and temperature settings
    - other settings: debug, timeout, workers, etc.

    Example:
        llm-quest benchmark --config benchmark_config.yaml
    """
    try:
        log_manager.setup(debug)

        # Load config from file
        if not config.exists():
            typer.echo(f"Config file does not exist: {config}", err=True)
            raise typer.Exit(code=1)

        log.info(f"Loading benchmark config from {config}")
        try:
            benchmark_config = BenchmarkConfig.from_yaml(str(config))
        except Exception as e:
            typer.echo(f"Failed to load config: {str(e)}", err=True)
            raise typer.Exit(code=1)

        # Override debug setting if specified
        if debug:
            benchmark_config.debug = debug

        # Log configuration
        log.info("Running benchmark with:")
        log.info(f"Quests: {benchmark_config.quests}")
        log.info(f"Agents: {[a.model for a in benchmark_config.agents]}")
        log.info(f"Quest timeout: {benchmark_config.quest_timeout}s")
        log.info(f"Output directory: {benchmark_config.output_dir}")

        # Set benchmark_id if not in config
        if not benchmark_config.benchmark_id:
            benchmark_config.benchmark_id = generate_benchmark_id("CLI_benchmark")

        # Run benchmark
        results = run_benchmark(benchmark_config)

        # Print summary
        print_summary(results)

        # Check for errors
        errors = [r for r in results if r["outcome"] == QuestOutcome.ERROR.name]
        if len(errors) == len(results):  # All quests errored
            log.error("All quests failed with errors")
            raise typer.Exit(code=2)
        elif errors:  # Some quests errored
            log.warning(f"{len(errors)} quests failed with errors")

    except typer.Exit:
        raise  # Re-raise typer.Exit without logging
    except Exception as e:
        typer.echo(f"Error during benchmark: {str(e)}", err=True)
        raise typer.Exit(code=2)


if __name__ == "__main__":
    app()
