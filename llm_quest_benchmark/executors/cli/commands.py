"""CLI commands for llm-quest-benchmark"""
import logging
import json
import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
import shutil
from datetime import datetime
from dotenv import load_dotenv

# Initialize quest registry early
from llm_quest_benchmark.core.quest_registry import get_registry
get_registry(reset_cache=True)
load_dotenv(dotenv_path=Path(__file__).resolve().parents[3] / ".env", override=False)

from llm_quest_benchmark.agents.agent_factory import create_agent
import typer

from llm_quest_benchmark.core.logging import LogManager
from llm_quest_benchmark.core.runner import run_quest_with_timeout
from llm_quest_benchmark.core.analyzer import analyze_quest_run, analyze_benchmark
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.executors.benchmark import run_benchmark, print_summary
from llm_quest_benchmark.renderers.terminal import RichRenderer
from llm_quest_benchmark.constants import (
    MODEL_CHOICES,
    DEFAULT_MODEL,
    DEFAULT_QUEST,
    DEFAULT_TEMPLATE,
    DEFAULT_TEMPERATURE,
    INFINITE_TIMEOUT,
    SYSTEM_ROLE_TEMPLATE,
    WEB_SERVER_HOST,
    WEB_SERVER_PORT,
)
from llm_quest_benchmark.schemas.config import AgentConfig, BenchmarkConfig
from llm_quest_benchmark.agents.human_player import HumanPlayer

# Initialize logging
log_manager = LogManager()
log = log_manager.get_logger()

app = typer.Typer(
    help="llm-quest: Command-line tools for LLM Quest Benchmark.",
    rich_markup_mode="rich",
)

def version_callback(value: bool):
    if value:
        typer.echo(f"llm-quest version 0.1.0")
        raise typer.Exit()


def _parse_run_dir_id(path: Path) -> int:
    """Parse run_<id> directory names for sorting."""
    try:
        return int(path.name.split("_", 1)[1])
    except (IndexError, ValueError):
        return -1


def _load_run_summary(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _coerce_choices(step: Dict[str, Any]) -> Dict[str, str]:
    """Normalize old/new step choice formats to {index: text} map."""
    choices = step.get("choices")
    if isinstance(choices, dict):
        return {str(k): str(v) for k, v in choices.items()}
    if isinstance(choices, list):
        return {str(i): c.get("text", "") for i, c in enumerate(choices, start=1) if isinstance(c, dict)}
    indexed = step.get("choices_indexed")
    if isinstance(indexed, list):
        return {
            str(c.get("index")): c.get("text", "")
            for c in indexed
            if isinstance(c, dict) and c.get("index") is not None
        }
    return {}


def _coerce_selected_choice(step: Dict[str, Any], choices_map: Dict[str, str]) -> Optional[Dict[str, str]]:
    """Extract selected choice from old/new step schema."""
    llm_decision = step.get("llm_decision") or {}
    if isinstance(llm_decision, dict):
        choice_map = llm_decision.get("choice")
        if isinstance(choice_map, dict) and choice_map:
            return {str(k): str(v) for k, v in choice_map.items()}

    selected_choice = step.get("selected_choice")
    if isinstance(selected_choice, dict):
        idx = selected_choice.get("index")
        text = selected_choice.get("text")
        if idx is not None and text is not None:
            return {str(idx): str(text)}

    action_index = step.get("action_index") or step.get("action")
    try:
        idx = str(int(action_index))
    except (TypeError, ValueError):
        return None
    if idx not in choices_map:
        return None
    return {idx: choices_map[idx]}

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
    run_summary: Optional[Path] = typer.Option(None, help="Path to run_summary.json."),
    agent: Optional[str] = typer.Option(None, help="Agent results folder name (e.g. llm_gpt-5-mini)."),
    quest: Optional[str] = typer.Option(None, help="Quest results folder name (e.g. Diehard)."),
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

        data = _load_run_summary(summary_path)
        steps = data.get("steps") or []
        outcome = data.get("outcome", "UNKNOWN")
        quest_name = data.get("quest_name", "unknown")
        agent_id = data.get("agent_id", "unknown")

        typer.echo(f"Run: {summary_path}")
        typer.echo(f"Quest: {quest_name}")
        typer.echo(f"Agent: {agent_id}")
        typer.echo(f"Outcome: {outcome}")
        typer.echo(f"Total Steps: {len(steps)}")

        decision_rows = []
        for step in steps:
            if not isinstance(step, dict):
                continue
            choices_map = _coerce_choices(step)
            if len(choices_map) <= 1:
                continue
            llm_decision = step.get("llm_decision") if isinstance(step.get("llm_decision"), dict) else {}
            decision_rows.append(
                {
                    "step": step.get("step"),
                    "observation": step.get("observation", ""),
                    "choices": choices_map,
                    "selected": _coerce_selected_choice(step, choices_map),
                    "analysis": llm_decision.get("analysis"),
                    "reasoning": llm_decision.get("reasoning"),
                    "is_default": bool(llm_decision.get("is_default", False)),
                }
            )

        typer.echo(f"Decision Steps: {len(decision_rows)}")
        if not decision_rows:
            return

        typer.echo("\nDecision Trace:")
        for row in decision_rows[:max_steps]:
            selected = row["selected"] or {}
            selected_str = ", ".join(f"{k}:{v}" for k, v in selected.items()) if selected else "none"
            typer.echo(f"- step {row['step']}: selected [{selected_str}] default={row['is_default']}")
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
            selected = last["selected"] or {}
            if selected:
                chosen_idx, chosen_text = next(iter(selected.items()))
                typer.echo(f"- selected: {chosen_idx}: {chosen_text}")

    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error analyzing run summary: {str(e)}", err=True)
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
    action_template: str = typer.Option(DEFAULT_TEMPLATE, help="Template to use for action prompts."),
    timeout: int = typer.Option(60, help="Timeout in seconds for run (0 for no timeout)."),
    skip: bool = typer.Option(True, help="Auto-select single choices without asking agent."),
    debug: bool = typer.Option(False, help="Enable debug logging and output, remove terminal UI."),
):
    """Run a quest with an LLM agent.

    This command runs a Space Rangers quest using an LLM agent. The agent will attempt to complete
    the quest by making decisions based on the quest text and available choices.

    Example:
        llm-quest run --quest quests/boat.qm --model sonnet --debug
    """
    try:
        log_manager.setup(debug)

        # Create agent config
        agent_config = AgentConfig(
            model=model,
            system_template=system_template,
            action_template=action_template,
            temperature=temperature,
            skip_single=skip,
            debug=debug
        )

        # Create agent
        agent = create_agent(
            model=model,
            system_template=system_template,
            action_template=action_template,
            temperature=temperature,
            skip_single=skip,
            debug=debug
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

            callbacks = [
                title_callback,
                game_state_callback,
                progress_callback,
                error_callback,
                close_callback
            ]

        timeout = timeout if timeout > 0 else 10**9
        result = run_quest_with_timeout(
                quest_path=str(quest),
                agent=agent,
                debug=debug,
                timeout=timeout,
                agent_config=agent_config,
                callbacks=callbacks
        )
        _handle_quest_outcome(result, "Quest run")

    except typer.Exit:
        raise  # Re-raise typer.Exit without logging
    except Exception as e:
        log.exception(f"Error during quest run: {e}")
        raise typer.Exit(code=2)

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
        log.info(f"Starting interactive quest play")
        log.debug(f"Quest file: {quest}")

        # Create interactive player
        player = HumanPlayer(skip_single=skip, debug=debug)

        # Run quest in interactive mode
        result = run_quest_with_timeout(
            quest_path=str(quest),
            agent=player,
            timeout=INFINITE_TIMEOUT,
            debug=debug
        )
        _handle_quest_outcome(result, "Quest play")

    except typer.Exit:
        raise  # Re-raise typer.Exit without logging
    except Exception as e:
        log.exception(f"Error during interactive play: {e}")
        raise typer.Exit(code=2)

@app.command()
def analyze(
    quest: Optional[str] = typer.Option(None, help="Name of the quest to analyze (e.g. 'boat.qm')."),
    benchmark: Optional[str] = typer.Option(None, help="Name of the benchmark to analyze (e.g. 'baseline')."),
    run_id: Optional[int] = typer.Option(None, help="Specific run ID to analyze in detail."),
    last: bool = typer.Option(False, help="Analyze the most recent quest run."),
    db: Path = typer.Option("metrics.db", help="Path to SQLite database."),
    export: Optional[Path] = typer.Option(None, help="Export results to JSON file."),
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
            # First check schema to handle older database versions
            cursor.execute("PRAGMA table_info(runs)")
            columns = [column[1] for column in cursor.fetchall()]
            
            # Construct query based on available columns
            select_fields = ["r.id", "r.quest_name", "r.start_time", "r.end_time", "r.agent_id", "r.agent_config"]
            if "outcome" in columns:
                select_fields.append("r.outcome")
            else:
                select_fields.append("'UNKNOWN' as outcome")
                
            if "reward" in columns:
                select_fields.append("r.reward")
            else:
                select_fields.append("0.0 as reward")
                
            if "run_duration" in columns:
                select_fields.append("r.run_duration")
            else:
                select_fields.append("NULL as run_duration")
                
            query = f'''
                SELECT {', '.join(select_fields)}
                FROM runs r
                WHERE r.id = ?
            '''
            cursor.execute(query, (run_id,))
            
            run = cursor.fetchone()
            if not run:
                typer.echo(f"Run ID {run_id} not found", err=True)
                raise typer.Exit(code=1)
                
            run_id, quest_name, start_time, end_time, agent_id, agent_config, outcome, reward, run_duration = run
            
            # Get steps for this run
            cursor.execute('''
                SELECT step, location_id, observation, choices, action, llm_response
                FROM steps
                WHERE run_id = ?
                ORDER BY step
            ''', (run_id,))
            
            steps = []
            step_count = 0
            success_choices = 0
            total_choices = 0
            
            for step_data in cursor.fetchall():
                step_count += 1
                step_num, location_id, obs, choices_json, action, llm_response = step_data
                choices = json.loads(choices_json) if choices_json else []
                total_choices += len(choices)
                if len(choices) == 1:
                    success_choices += 1
                    
                step = {
                    "step": step_num,
                    "location_id": location_id,
                    "observation": obs,
                    "choices": choices,
                    "action": action,
                    "llm_response": json.loads(llm_response) if llm_response else None
                }
                steps.append(step)
            
            run_data = {
                "run_id": run_id,
                "quest_name": quest_name,
                "start_time": start_time,
                "end_time": end_time,
                "agent_id": agent_id,
                "agent_config": json.loads(agent_config) if agent_config else None,
                "outcome": outcome,
                "reward": reward,
                "run_duration": run_duration,
                "steps": steps,
                "stats": {
                    "total_steps": step_count,
                    "total_choices": total_choices,
                    "auto_choices": success_choices,
                    "decision_points": total_choices - success_choices
                }
            }
            
            # Export if requested
            if export:
                with open(export, 'w') as f:
                    json.dump(run_data, f, indent=2)
                typer.echo(f"Results exported to {export}")
            
            # Print human-readable summary based on format
            if format == "summary":
                typer.echo("\n📊 Run Summary")
                typer.echo("==============")
                typer.echo(f"Run ID: {run_id}")
                typer.echo(f"Quest: {quest_name}")
                typer.echo(f"Agent: {agent_id}")
                typer.echo(f"Start Time: {start_time}")
                typer.echo(f"Duration: {run_duration:.2f} seconds")
                typer.echo(f"Outcome: {outcome}")
                typer.echo(f"Reward: {reward}")
                typer.echo(f"Total Steps: {step_count}")
                typer.echo(f"Decision Points: {total_choices - success_choices}")
                
            elif format == "detail":
                typer.echo("\n📊 Run Details")
                typer.echo("=============")
                typer.echo(f"Run ID: {run_id}")
                typer.echo(f"Quest: {quest_name}")
                typer.echo(f"Agent: {agent_id}")
                typer.echo(f"Start Time: {start_time}")
                typer.echo(f"End Time: {end_time}")
                typer.echo(f"Duration: {run_duration:.2f} seconds")
                typer.echo(f"Outcome: {outcome}")
                typer.echo(f"Reward: {reward}")
                
                # Agent config details if available
                if run_data.get('agent_config'):
                    typer.echo("\nAgent Configuration:")
                    for key, value in run_data['agent_config'].items():
                        typer.echo(f"  {key}: {value}")
                
                # Step details
                typer.echo(f"\nSteps ({len(steps)} total):")
                for i, step in enumerate(steps, 1):
                    typer.echo(f"\n🔹 Step {i}:")
                    typer.echo(f"  Location: {step['location_id']}")
                    
                    # Truncate observation for readability
                    obs = step['observation']
                    if len(obs) > 100:
                        obs = obs[:97] + "..."
                    typer.echo(f"  Observation: {obs}")
                    
                    # Show choices
                    if step['choices']:
                        typer.echo(f"  Choices ({len(step['choices'])}):")
                        for j, choice in enumerate(step['choices'], 1):
                            choice_text = choice['text']
                            if len(choice_text) > 50:
                                choice_text = choice_text[:47] + "..."
                            typer.echo(f"    {j}. {choice_text}")
                    
                    typer.echo(f"  Action: {step['action']}")
                    
                    # Show LLM reasoning if available and debug is enabled
                    if debug and step.get('llm_response'):
                        llm_resp = step['llm_response']
                        if isinstance(llm_resp, dict) and llm_resp.get('reasoning'):
                            typer.echo(f"  Reasoning: {llm_resp['reasoning']}")
                
            elif format == "compact":
                typer.echo(f"Run {run_id}: {quest_name} - {outcome} (Reward: {reward}) - Steps: {step_count} - Agent: {agent_id}")
                            
        # Analyze quest runs
        elif quest:
            results = analyze_quest_run(quest, db, debug)

            # Export if requested
            if export:
                with open(export, 'w') as f:
                    json.dump(results, f, indent=2)
                typer.echo(f"Results exported to {export}")

            # Print human-readable summary based on format
            if format == "summary" or format == "compact":
                typer.echo("\n📊 Quest Run Summary")
                typer.echo("===================")
                typer.echo(f"Quest: {results['quest_name']}")
                typer.echo(f"Total Runs: {results['total_runs']}")
                
                # Success rate calculation
                success_count = results['outcomes'].get('SUCCESS', 0)
                success_rate = (success_count / results['total_runs'] * 100) if results['total_runs'] > 0 else 0
                typer.echo(f"Success Rate: {success_rate:.1f}%")
                
                # Outcome breakdown
                typer.echo("\nOutcomes:")
                for outcome, count in results['outcomes'].items():
                    typer.echo(f"  {outcome}: {count} ({count/results['total_runs']*100:.1f}%)")
                
                # Agent performance
                agents = {}
                for run in results['runs']:
                    agent = run.get('model', 'unknown')
                    if agent not in agents:
                        agents[agent] = {'total': 0, 'success': 0}
                    
                    agents[agent]['total'] += 1
                    if run.get('outcome') == 'SUCCESS':
                        agents[agent]['success'] += 1
                
                if agents and format == "summary":
                    typer.echo("\nAgent Performance:")
                    for agent, stats in agents.items():
                        success_rate = (stats['success'] / stats['total'] * 100) if stats['total'] > 0 else 0
                        typer.echo(f"  {agent}: {stats['success']}/{stats['total']} ({success_rate:.1f}%)")
            
            if format == "detail":
                # Print detailed run information
                typer.echo("\n📊 Run Details")
                typer.echo("=============")
                
                for i, run in enumerate(results['runs'], 1):
                    typer.echo(f"\n🔸 Run {i} (ID: {run.get('id', 'unknown')}):")
                    typer.echo(f"  Start Time: {run['start_time']}")
                    typer.echo(f"  Agent: {run.get('model', 'unknown')}")
                    typer.echo(f"  Outcome: {run['outcome']}")
                    typer.echo(f"  Reward: {run['reward']}")
                    
                    # Only show steps in debug mode to avoid output overload
                    if debug and run.get('steps'):
                        typer.echo(f"\n  Steps ({len(run['steps'])} total):")
                        for step in run['steps']:
                            typer.echo(f"    Step {step['step']}: Action {step['action']}")

        # Analyze benchmark results
        else:
            results = analyze_benchmark(db, benchmark, debug)
            
            # Export if requested
            if export and results:
                with open(export, 'w') as f:
                    json.dump(results, f, indent=2)
                typer.echo(f"Results exported to {export}")

    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        log.exception(f"Error during analysis: {e}")
        raise typer.Exit(code=1)
        
    finally:
        if 'conn' in locals():
            conn.close()
            
@app.command()
def cleanup(
    db_path: Path = typer.Option("metrics.db", help="Path to SQLite database file."),
    older_than: Optional[str] = typer.Option(None, help="ISO date (YYYY-MM-DD) to delete records older than this date."),
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
        cursor.execute("SELECT count(*) FROM steps")
        initial_steps = cursor.fetchone()[0]
        
        deleted_runs = 0
        deleted_steps = 0
        
        # Delete by date
        if older_than:
            try:
                # Parse date string
                cutoff_date = datetime.fromisoformat(older_than)
                typer.echo(f"Deleting records older than {cutoff_date.strftime('%Y-%m-%d')}")
                
                # Get run IDs to delete
                cursor.execute("SELECT id FROM runs WHERE start_time < ?", (cutoff_date.isoformat(),))
                run_ids = [row[0] for row in cursor.fetchall()]
                
                # Delete steps first
                if run_ids:
                    placeholders = ','.join('?' for _ in run_ids)
                    cursor.execute(f"DELETE FROM steps WHERE run_id IN ({placeholders})", run_ids)
                    deleted_steps = cursor.rowcount
                    
                    # Then delete runs
                    cursor.execute(f"DELETE FROM runs WHERE id IN ({placeholders})", run_ids)
                    deleted_runs = cursor.rowcount
                
                conn.commit()
                typer.echo(f"Deleted {deleted_runs} runs and {deleted_steps} steps")
                
            except ValueError:
                typer.echo(f"Invalid date format: {older_than}. Use YYYY-MM-DD format.", err=True)
                raise typer.Exit(code=1)
                
        # Delete all records
        elif all:
            typer.echo("Deleting all records from database")
            
            # Delete steps first (due to foreign key constraints)
            cursor.execute("DELETE FROM steps")
            deleted_steps = cursor.rowcount
            
            # Then delete runs
            cursor.execute("DELETE FROM runs")
            deleted_runs = cursor.rowcount
            
            conn.commit()
            typer.echo(f"Deleted {deleted_runs} runs and {deleted_steps} steps")
            
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
        cursor.execute("SELECT count(*) FROM steps")
        final_steps = cursor.fetchone()[0]
        
        typer.echo(f"\nSummary:")
        typer.echo(f"Runs: {initial_runs} -> {final_runs} ({initial_runs - final_runs} removed)")
        typer.echo(f"Steps: {initial_steps} -> {final_steps} ({initial_steps - final_steps} removed)")
        
    except Exception as e:
        typer.echo(f"Error during cleanup: {str(e)}", err=True)
        raise typer.Exit(code=1)
    finally:
        if 'conn' in locals():
            conn.close()

@app.command()
def benchmark(
    config: Path = typer.Option(..., help="Path to benchmark configuration YAML file."),
    debug: bool = typer.Option(False, help="Enable debug logging and output."),
):
    """Run benchmark evaluation on a set of quests.

    This command runs benchmark evaluation using a YAML configuration file that specifies:
    - quests: list of quest files or directories to test
    - agents: list of agents with their model, template, and temperature settings
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
        log.info(f"Running benchmark with:")
        log.info(f"Quests: {benchmark_config.quests}")
        log.info(f"Agents: {[a.model for a in benchmark_config.agents]}")
        log.info(f"Quest timeout: {benchmark_config.quest_timeout}s")
        log.info(f"Output directory: {benchmark_config.output_dir}")

        # Set benchmark_id if not in config
        if not benchmark_config.benchmark_id:
            benchmark_config.benchmark_id = f"CLI_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
        # Run benchmark
        results = run_benchmark(benchmark_config)

        # Print summary
        print_summary(results)

        # Check for errors
        errors = [r for r in results if r['outcome'] == QuestOutcome.ERROR.name]
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

@app.command()
def server(
    host: str = typer.Option(WEB_SERVER_HOST, help="Host to run the server on"),
    port: int = typer.Option(WEB_SERVER_PORT, help="Port to run the server on (will auto-increment if taken)"),
    debug: bool = typer.Option(False, help="Enable debug mode"),
    workers: int = typer.Option(4, help="Number of worker processes (only used in production mode)"),
    production: bool = typer.Option(False, help="Run in production mode using gunicorn")
):
    """Start the Flask web interface server.

    This command starts the Flask web interface for running and analyzing quests.
    It uses Flask's built-in server which is suitable for local development.

    For production use, set the --production flag to use gunicorn with multiple workers.

    Example:
        llm-quest server  # Run server on default port (8000)
        llm-quest server --port 5000  # Run on a different port
        llm-quest server --debug  # Run with debug mode enabled
        llm-quest server --production --workers 8  # Run in production mode with 8 workers
    """
    try:
        # Setup logging
        log_manager.setup(debug)
        log.info("Starting web interface server")

        print(f"Starting server on http://{host}:{port}")

        # Use server_logic to start the server
        from llm_quest_benchmark.executors.cli.logic.server_logic import start_server
        success, message = start_server(host, port, debug, workers, production)

        if not success:
            raise Exception(message)

    except Exception as e:
        log.exception(f"Error starting server: {e}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
