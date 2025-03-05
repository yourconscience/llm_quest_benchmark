"""CLI commands for llm-quest-benchmark"""
import logging
import click
import json
import sqlite3
from pathlib import Path
from typing import Optional, List
import socket
import shutil
from datetime import datetime

# Initialize quest registry early
from llm_quest_benchmark.core.quest_registry import get_registry
get_registry(reset_cache=True)

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
    PROMPT_TEMPLATES_DIR,
    SYSTEM_TEMPLATES_DIR,
    ACTION_TEMPLATES_DIR,
)
from llm_quest_benchmark.schemas.config import AgentConfig, BenchmarkConfig
from llm_quest_benchmark.schemas.agent import AgentConfig as AgentSchema
from llm_quest_benchmark.agents.human_player import HumanPlayer
from llm_quest_benchmark.agents.agent_manager import AgentManager
from llm_quest_benchmark.web.app import create_app

# Initialize logging
log_manager = LogManager()
log = log_manager.get_logger()

app = typer.Typer(
    help="llm-quest: Command-line tools for LLM Quest Benchmark.",
    rich_markup_mode="rich",
)

# Create subcommand for agent management
agents_app = typer.Typer(
    help="Manage agent configurations",
    rich_markup_mode="rich",
)
app.add_typer(agents_app, name="agents")

# Create subcommand for template management
templates_app = typer.Typer(
    help="Manage prompt templates",
    rich_markup_mode="rich",
)
app.add_typer(templates_app, name="templates")

def version_callback(value: bool):
    if value:
        typer.echo(f"llm-quest version 0.1.0")
        raise typer.Exit()

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
    agent_id: Optional[str] = typer.Option(None, "--agent", "-a", help="Agent ID to use from saved agents"),
    model: Optional[str] = typer.Option(None, help=f"Model for the LLM agent (choices: {', '.join(MODEL_CHOICES)})."),
    temperature: Optional[float] = typer.Option(None, help="Temperature for LLM sampling"),
    system_template: Optional[str] = typer.Option(None, help="Template to use for system instructions."),
    action_template: Optional[str] = typer.Option(None, help="Template to use for action prompts."),
    timeout: int = typer.Option(60, help="Timeout in seconds for run (0 for no timeout)."),
    skip: bool = typer.Option(True, help="Auto-select single choices without asking agent."),
    debug: bool = typer.Option(False, help="Enable debug logging and output, remove terminal UI."),
):
    """Run a quest with an LLM agent.

    This command runs a Space Rangers quest using an LLM agent. The agent will attempt to complete
    the quest by making decisions based on the quest text and available choices.

    You can use a saved agent configuration with --agent or specify parameters directly.

    Example:
        llm-quest run --quest quests/boat.qm --model gpt-4o-mini --debug
        llm-quest run --quest quests/boat.qm --agent my-custom-agent
    """
    try:
        log_manager.setup(debug)

        # Create agent
        if agent_id:
            # Use saved agent configuration
            agent_manager = AgentManager()
            saved_agent = agent_manager.get_agent(agent_id)
            
            if not saved_agent:
                typer.echo(f"Agent {agent_id} not found", err=True)
                raise typer.Exit(code=1)
            
            log.info(f"Using saved agent: {agent_id}")
            
            # Import create_agent_from_id
            from llm_quest_benchmark.agents.agent_factory import create_agent_from_id
            
            # Create agent from saved configuration
            agent = create_agent_from_id(agent_id, skip_single=skip, debug=debug)
            
            if not agent:
                typer.echo(f"Failed to create agent from {agent_id}", err=True)
                raise typer.Exit(code=1)
            
            # Set up model parameters from saved agent for agent_config
            model = saved_agent.model
            system_template = saved_agent.system_template or SYSTEM_ROLE_TEMPLATE
            action_template = saved_agent.action_template or DEFAULT_TEMPLATE
            temperature = saved_agent.temperature
            
            agent_config = AgentConfig(
                model=model,
                system_template=system_template,
                action_template=action_template,
                temperature=temperature,
                skip_single=skip,
                debug=debug
            )
        else:
            # Use parameters from command line
            if not model:
                model = DEFAULT_MODEL
                log.info(f"No model specified, using default: {model}")
            
            if not system_template:
                system_template = SYSTEM_ROLE_TEMPLATE
            
            if not action_template:
                action_template = DEFAULT_TEMPLATE
            
            if temperature is None:
                temperature = DEFAULT_TEMPERATURE
            
            agent_config = AgentConfig(
                model=model,
                system_template=system_template,
                action_template=action_template,
                temperature=temperature,
                skip_single=skip,
                debug=debug
            )

            # Create agent from parameters
            from llm_quest_benchmark.agents.agent_factory import create_agent
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
    """Start the web interface server.

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

# Agent management commands
@agents_app.command(name="list")
def list_agents():
    """List all available agents"""
    try:
        agent_manager = AgentManager()
        agents = agent_manager.list_agents()
        
        if not agents:
            typer.echo("No agents found")
            return
        
        typer.echo("Available agents:")
        for agent_id in agents:
            agent = agent_manager.get_agent(agent_id)
            if agent:
                # Format temperature with 1 decimal place
                temp = f"{agent.temperature:.1f}"
                typer.echo(f"  {agent_id} - {agent.model} (temp: {temp})")
            else:
                typer.echo(f"  {agent_id} - Error loading agent config")
    except Exception as e:
        log.exception(f"Error listing agents: {e}")
        raise typer.Exit(code=1)

@agents_app.command(name="show")
def show_agent(
    agent_id: str = typer.Argument(..., help="Agent ID to display"),
    template: bool = typer.Option(False, "--template", "-t", help="Show templates")
):
    """Show details for a specific agent"""
    try:
        agent_manager = AgentManager()
        agent = agent_manager.get_agent(agent_id)
        
        if not agent:
            typer.echo(f"Agent {agent_id} not found")
            return
        
        typer.echo(f"Agent ID: {agent.agent_id}")
        typer.echo(f"Model: {agent.model}")
        typer.echo(f"Temperature: {agent.temperature}")
        
        if agent.description:
            typer.echo(f"Description: {agent.description}")
        
        if agent.max_tokens:
            typer.echo(f"Max Tokens: {agent.max_tokens}")
        
        if agent.top_p:
            typer.echo(f"Top P: {agent.top_p}")
        
        if agent.additional_params:
            typer.echo(f"Additional Parameters: {agent.additional_params}")
        
        if template:
            typer.echo("\nSystem Template:")
            typer.echo("---------------------")
            typer.echo(agent.system_template or "[Not set]")
            
            typer.echo("\nAction Template:")
            typer.echo("---------------------")
            typer.echo(agent.action_template or "[Not set]")
    except Exception as e:
        log.exception(f"Error showing agent: {e}")
        raise typer.Exit(code=1)

@agents_app.command(name="new")
def new_agent(
    agent_id: str = typer.Option(..., "--id", help="Unique ID for the agent"),
    model: str = typer.Option(..., "--model", "-m", help="Model to use"),
    temperature: float = typer.Option(0.7, "--temperature", "-t", help="Temperature for the model"),
    system_template: Optional[str] = typer.Option(None, "--system-template", "-s", help="Path to system prompt template file"),
    action_template: Optional[str] = typer.Option(None, "--action-template", "-a", help="Path to action prompt template file"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Description of the agent"),
    from_yaml: Optional[str] = typer.Option(None, "--yaml", help="Create from YAML config file")
):
    """Create a new agent configuration"""
    try:
        agent_manager = AgentManager()
        
        if from_yaml:
            # Create agent from YAML config
            if not os.path.exists(from_yaml):
                typer.echo(f"Config file not found: {from_yaml}")
                return
            
            try:
                import yaml
                with open(from_yaml, "r") as f:
                    config = yaml.safe_load(f)
                
                if not isinstance(config, dict):
                    typer.echo("Invalid YAML format, expected a dictionary")
                    return
                
                # Create agent from config
                agent_config = AgentSchema(**config)
                success = agent_manager.create_agent(agent_config)
                
                if success:
                    typer.echo(f"Created agent {agent_config.agent_id} from YAML config")
                else:
                    typer.echo(f"Failed to create agent from YAML config")
                
                return
            except Exception as e:
                typer.echo(f"Error loading YAML config: {e}")
                return
        
        # Read templates if provided
        system_template_content = None
        if system_template:
            if os.path.exists(system_template):
                try:
                    with open(system_template, "r", encoding="utf-8") as f:
                        system_template_content = f.read()
                except Exception as e:
                    typer.echo(f"Error reading system template: {e}")
                    return
            else:
                typer.echo(f"System template file not found: {system_template}")
                return
        
        action_template_content = None
        if action_template:
            if os.path.exists(action_template):
                try:
                    with open(action_template, "r", encoding="utf-8") as f:
                        action_template_content = f.read()
                except Exception as e:
                    typer.echo(f"Error reading action template: {e}")
                    return
            else:
                typer.echo(f"Action template file not found: {action_template}")
                return
        
        # Create the agent config
        agent_config = AgentSchema(
            agent_id=agent_id,
            model=model,
            temperature=temperature,
            system_template=system_template_content,
            action_template=action_template_content,
            description=description
        )
        
        # Create the agent
        success = agent_manager.create_agent(agent_config)
        
        if success:
            typer.echo(f"Created agent {agent_id}")
        else:
            typer.echo(f"Failed to create agent {agent_id}")
    except Exception as e:
        log.exception(f"Error creating agent: {e}")
        raise typer.Exit(code=1)

@agents_app.command(name="edit")
def edit_agent(
    agent_id: str = typer.Argument(..., help="Agent ID to edit"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="New model to use"),
    temperature: Optional[float] = typer.Option(None, "--temperature", "-t", help="New temperature for the model"),
    system_template: Optional[str] = typer.Option(None, "--system-template", "-s", help="Path to new system prompt template file"),
    action_template: Optional[str] = typer.Option(None, "--action-template", "-a", help="Path to new action prompt template file"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="New description of the agent")
):
    """Edit an existing agent configuration"""
    try:
        agent_manager = AgentManager()
        agent = agent_manager.get_agent(agent_id)
        
        if not agent:
            typer.echo(f"Agent {agent_id} not found")
            return
        
        # Update agent fields if provided
        if model:
            agent.model = model
        
        if temperature is not None:
            agent.temperature = temperature
        
        if description is not None:
            agent.description = description
        
        # Update templates if provided
        if system_template:
            if os.path.exists(system_template):
                try:
                    with open(system_template, "r", encoding="utf-8") as f:
                        agent.system_template = f.read()
                except Exception as e:
                    typer.echo(f"Error reading system template: {e}")
                    return
            else:
                typer.echo(f"System template file not found: {system_template}")
                return
        
        if action_template:
            if os.path.exists(action_template):
                try:
                    with open(action_template, "r", encoding="utf-8") as f:
                        agent.action_template = f.read()
                except Exception as e:
                    typer.echo(f"Error reading action template: {e}")
                    return
            else:
                typer.echo(f"Action template file not found: {action_template}")
                return
        
        # Update the agent
        success = agent_manager.update_agent(agent)
        
        if success:
            typer.echo(f"Updated agent {agent_id}")
        else:
            typer.echo(f"Failed to update agent {agent_id}")
    except Exception as e:
        log.exception(f"Error editing agent: {e}")
        raise typer.Exit(code=1)

@agents_app.command(name="delete")
def delete_agent(
    agent_id: str = typer.Argument(..., help="Agent ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Force deletion without confirmation")
):
    """Delete an agent configuration"""
    try:
        agent_manager = AgentManager()
        agent = agent_manager.get_agent(agent_id)
        
        if not agent:
            typer.echo(f"Agent {agent_id} not found")
            return
        
        # Confirm deletion
        if not force and not typer.confirm(f"Are you sure you want to delete agent {agent_id}?"):
            typer.echo("Deletion cancelled")
            return
        
        # Delete the agent
        success = agent_manager.delete_agent(agent_id)
        
        if success:
            typer.echo(f"Deleted agent {agent_id}")
        else:
            typer.echo(f"Failed to delete agent {agent_id}")
    except Exception as e:
        log.exception(f"Error deleting agent: {e}")
        raise typer.Exit(code=1)

@agents_app.command(name="create-defaults")
def create_default_agents():
    """Create default agent configurations"""
    try:
        agent_manager = AgentManager()
        agent_manager.create_default_agents()
        typer.echo("Created default agents")
        list_agents()
    except Exception as e:
        log.exception(f"Error creating default agents: {e}")
        raise typer.Exit(code=1)

@agents_app.command(name="set-memory")
def set_agent_memory(
    agent_id: str = typer.Argument(..., help="Agent ID to modify"),
    memory_type: str = typer.Argument(..., help="Memory type (message_history or summary)"),
    max_history: int = typer.Argument(10, help="Maximum number of history entries")
):
    """Set memory configuration for an agent"""
    try:
        if memory_type not in ["message_history", "summary"]:
            typer.echo(f"Invalid memory type: {memory_type}. Must be 'message_history' or 'summary'.", err=True)
            raise typer.Exit(code=1)
            
        if max_history < 1:
            typer.echo(f"Invalid max_history: {max_history}. Must be greater than 0.", err=True)
            raise typer.Exit(code=1)
            
        agent_manager = AgentManager()
        agent = agent_manager.get_agent(agent_id)
        
        if not agent:
            typer.echo(f"Agent {agent_id} not found", err=True)
            raise typer.Exit(code=1)
        
        # Create memory config
        from llm_quest_benchmark.schemas.agent import MemoryConfig
        memory_config = MemoryConfig(
            type=memory_type,
            max_history=max_history
        )
        
        # Update agent memory
        agent.memory = memory_config
        success = agent_manager.update_agent(agent)
        
        if success:
            typer.echo(f"Updated memory configuration for agent {agent_id}")
            typer.echo(f"Memory type: {memory_type}")
            typer.echo(f"Max history: {max_history}")
        else:
            typer.echo(f"Failed to update memory configuration for agent {agent_id}", err=True)
            
    except Exception as e:
        log.exception(f"Error setting agent memory: {e}")
        raise typer.Exit(code=1)

@agents_app.command(name="add-tool")
def add_agent_tool(
    agent_id: str = typer.Argument(..., help="Agent ID to modify"),
    tool: str = typer.Argument(..., help="Tool to add (e.g., calculator)")
):
    """Add a tool to an agent"""
    try:
        # Currently only support 'calculator' tool
        if tool != "calculator":
            typer.echo(f"Invalid tool: {tool}. Currently only 'calculator' is supported.", err=True)
            raise typer.Exit(code=1)
            
        agent_manager = AgentManager()
        agent = agent_manager.get_agent(agent_id)
        
        if not agent:
            typer.echo(f"Agent {agent_id} not found", err=True)
            raise typer.Exit(code=1)
        
        # Initialize tools list if not exists
        if agent.tools is None:
            agent.tools = []
            
        # Check if tool already exists
        if tool in agent.tools:
            typer.echo(f"Tool {tool} already added to agent {agent_id}")
            return
            
        # Add tool
        agent.tools.append(tool)
        success = agent_manager.update_agent(agent)
        
        if success:
            typer.echo(f"Added tool {tool} to agent {agent_id}")
        else:
            typer.echo(f"Failed to add tool {tool} to agent {agent_id}", err=True)
            
    except Exception as e:
        log.exception(f"Error adding tool to agent: {e}")
        raise typer.Exit(code=1)

@agents_app.command(name="remove-tool")
def remove_agent_tool(
    agent_id: str = typer.Argument(..., help="Agent ID to modify"),
    tool: str = typer.Argument(..., help="Tool to remove (e.g., calculator)")
):
    """Remove a tool from an agent"""
    try:
        agent_manager = AgentManager()
        agent = agent_manager.get_agent(agent_id)
        
        if not agent:
            typer.echo(f"Agent {agent_id} not found", err=True)
            raise typer.Exit(code=1)
        
        # Check if agent has tools
        if not agent.tools:
            typer.echo(f"Agent {agent_id} has no tools")
            return
            
        # Check if agent has the tool
        if tool not in agent.tools:
            typer.echo(f"Agent {agent_id} does not have tool {tool}")
            return
            
        # Remove tool
        agent.tools.remove(tool)
        success = agent_manager.update_agent(agent)
        
        if success:
            typer.echo(f"Removed tool {tool} from agent {agent_id}")
        else:
            typer.echo(f"Failed to remove tool {tool} from agent {agent_id}", err=True)
            
    except Exception as e:
        log.exception(f"Error removing tool from agent: {e}")
        raise typer.Exit(code=1)

# Template management commands
@templates_app.command(name="list")
def list_templates(
    template_type: str = typer.Option("all", "--type", "-t", help="Template type (all, system, action)")
):
    """List available templates"""
    try:
        if template_type not in ["all", "system", "action"]:
            typer.echo(f"Invalid template type: {template_type}. Must be 'all', 'system', or 'action'.", err=True)
            raise typer.Exit(code=1)
        
        system_dir = SYSTEM_TEMPLATES_DIR
        action_dir = ACTION_TEMPLATES_DIR
        
        # Ensure directories exist
        system_dir.mkdir(parents=True, exist_ok=True)
        action_dir.mkdir(parents=True, exist_ok=True)
        
        # List system templates if requested
        if template_type in ["all", "system"]:
            typer.echo("System Templates:")
            system_templates = list(system_dir.glob("*.jinja"))
            if system_templates:
                for template in sorted(system_templates):
                    typer.echo(f"  {template.name}")
            else:
                typer.echo("  No system templates found")
        
        # List action templates if requested
        if template_type in ["all", "action"]:
            typer.echo("\nAction Templates:")
            action_templates = list(action_dir.glob("*.jinja"))
            if action_templates:
                for template in sorted(action_templates):
                    typer.echo(f"  {template.name}")
            else:
                typer.echo("  No action templates found")
                
    except Exception as e:
        log.exception(f"Error listing templates: {e}")
        raise typer.Exit(code=1)

@templates_app.command(name="show")
def show_template(
    template_name: str = typer.Argument(..., help="Template name"),
    template_type: str = typer.Option(None, "--type", "-t", help="Template type (system or action)")
):
    """Show the contents of a template"""
    try:
        # If template type not specified, try to infer it
        if not template_type:
            if not "/" in template_name and not "\\" in template_name:
                # Try both directories
                system_path = SYSTEM_TEMPLATES_DIR / template_name
                action_path = ACTION_TEMPLATES_DIR / template_name
                
                if system_path.exists():
                    template_type = "system"
                    template_path = system_path
                elif action_path.exists():
                    template_type = "action"
                    template_path = action_path
                else:
                    typer.echo(f"Template {template_name} not found in system or action directories.", err=True)
                    typer.echo("Specify the template type with --type or use the format 'system/template.jinja'", err=True)
                    raise typer.Exit(code=1)
            else:
                # Template includes path information
                full_path = PROMPT_TEMPLATES_DIR / template_name
                if not full_path.exists():
                    typer.echo(f"Template {template_name} not found.", err=True)
                    raise typer.Exit(code=1)
                template_path = full_path
        else:
            # Template type specified
            if template_type == "system":
                template_path = SYSTEM_TEMPLATES_DIR / template_name
            elif template_type == "action":
                template_path = ACTION_TEMPLATES_DIR / template_name
            else:
                typer.echo(f"Invalid template type: {template_type}. Must be 'system' or 'action'.", err=True)
                raise typer.Exit(code=1)
        
        # Check if template exists
        if not template_path.exists():
            typer.echo(f"Template {template_path} not found.", err=True)
            raise typer.Exit(code=1)
        
        # Show template content
        template_content = template_path.read_text(encoding="utf-8")
        typer.echo(f"Template: {template_path.relative_to(PROMPT_TEMPLATES_DIR.parent)}")
        typer.echo("-" * 40)
        typer.echo(template_content)
                
    except Exception as e:
        log.exception(f"Error showing template: {e}")
        raise typer.Exit(code=1)

@templates_app.command(name="new")
def new_template(
    template_name: str = typer.Argument(..., help="Template name (without .jinja extension)"),
    template_type: str = typer.Option("action", "--type", "-t", help="Template type (system or action)"),
    editor: bool = typer.Option(False, "--editor", "-e", help="Open in default editor after creation"),
    based_on: Optional[str] = typer.Option(None, "--based-on", "-b", help="Base on existing template")
):
    """Create a new template"""
    try:
        # Ensure template has .jinja extension
        if not template_name.endswith(".jinja"):
            template_name = f"{template_name}.jinja"
        
        # Determine target directory
        if template_type == "system":
            target_dir = SYSTEM_TEMPLATES_DIR
        elif template_type == "action":
            target_dir = ACTION_TEMPLATES_DIR
        else:
            typer.echo(f"Invalid template type: {template_type}. Must be 'system' or 'action'.", err=True)
            raise typer.Exit(code=1)
        
        # Ensure directory exists
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if template already exists
        target_path = target_dir / template_name
        if target_path.exists():
            if not typer.confirm(f"Template {target_path} already exists. Overwrite?"):
                typer.echo("Template creation cancelled.")
                return
        
        # Determine initial content
        if based_on:
            # Try to load base template
            base_template_path = None
            
            # Check if base template includes path
            if "/" in based_on or "\\" in based_on:
                base_template_path = PROMPT_TEMPLATES_DIR / based_on
                if not base_template_path.exists():
                    typer.echo(f"Base template {based_on} not found.", err=True)
                    raise typer.Exit(code=1)
            else:
                # Try both directories
                system_path = SYSTEM_TEMPLATES_DIR / based_on
                action_path = ACTION_TEMPLATES_DIR / based_on
                
                if system_path.exists():
                    base_template_path = system_path
                elif action_path.exists():
                    base_template_path = action_path
                else:
                    typer.echo(f"Base template {based_on} not found in system or action directories.", err=True)
                    raise typer.Exit(code=1)
            
            # Load base template content
            initial_content = base_template_path.read_text(encoding="utf-8")
        else:
            # Create template with helpful comments based on type
            if template_type == "system":
                initial_content = """{# System prompt template for LLM agent #}
{# This template is used to generate the system prompt for the LLM agent #}
{# Available variables: None #}

You are an experienced interactive fiction player. Your capabilities include:

1. Dynamic Goal Recognition: Infer objectives from narrative context
2. Clue Chaining: Connect information across scenes
3. Consequence Forecasting: Predict 2-3 steps ahead for each action
4. Narrative Consistency: Maintain character/story logic

Follow these principles:
- Treat each choice as part of an unfolding mystery
- Track objects/characters/relationships as state components
- Consider both practical and thematic implications
- Admit uncertainty when clues are ambiguous
"""
            else:  # action template
                initial_content = """{# Action prompt template for LLM agent #}
{# This template is used to generate the action prompt for each step #}
{# Available variables:
   - observation: The text description of the current state
   - choices: List of available choices as dicts with 'text' key
#}

Current story state:
{{ observation }}

Available actions:
{% for choice in choices %}
{{ loop.index }}. {{ choice.text }}
{% endfor %}

Analyze briefly:
1. Context: What's happening now?
2. Goal: What's the current objective?
3. Options: What could each choice lead to?

Your response should be exactly in this JSON format:
```json
{
    "analysis": "<brief analysis of the situation>",
    "reasoning": "<explanation of your choice>",
    "result": <action_number>
}
```
"""
        
        # Write template to file
        target_path.write_text(initial_content, encoding="utf-8")
        typer.echo(f"Template {target_path} created successfully.")
        
        # Open in editor if requested
        if editor:
            import subprocess
            import os
            import platform
            
            try:
                if platform.system() == 'Windows':
                    os.startfile(target_path)
                elif platform.system() == 'Darwin':  # macOS
                    subprocess.run(['open', target_path])
                else:  # Linux and other Unix-like systems
                    subprocess.run(['xdg-open', target_path])
            except Exception as e:
                typer.echo(f"Error opening editor: {e}", err=True)
                
    except Exception as e:
        log.exception(f"Error creating template: {e}")
        raise typer.Exit(code=1)

@templates_app.command(name="delete")
def delete_template(
    template_name: str = typer.Argument(..., help="Template name"),
    template_type: str = typer.Option(None, "--type", "-t", help="Template type (system or action)"),
    force: bool = typer.Option(False, "--force", "-f", help="Force deletion without confirmation")
):
    """Delete a template"""
    try:
        # Normalize template name
        if not template_name.endswith(".jinja"):
            template_name = f"{template_name}.jinja"
        
        # If template type not specified, try to infer it
        if not template_type:
            if not "/" in template_name and not "\\" in template_name:
                # Try both directories
                system_path = SYSTEM_TEMPLATES_DIR / template_name
                action_path = ACTION_TEMPLATES_DIR / template_name
                
                if system_path.exists():
                    template_type = "system"
                    template_path = system_path
                elif action_path.exists():
                    template_type = "action"
                    template_path = action_path
                else:
                    typer.echo(f"Template {template_name} not found in system or action directories.", err=True)
                    typer.echo("Specify the template type with --type or use the format 'system/template.jinja'", err=True)
                    raise typer.Exit(code=1)
            else:
                # Template includes path information
                full_path = PROMPT_TEMPLATES_DIR / template_name
                if not full_path.exists():
                    typer.echo(f"Template {template_name} not found.", err=True)
                    raise typer.Exit(code=1)
                template_path = full_path
        else:
            # Template type specified
            if template_type == "system":
                template_path = SYSTEM_TEMPLATES_DIR / template_name
            elif template_type == "action":
                template_path = ACTION_TEMPLATES_DIR / template_name
            else:
                typer.echo(f"Invalid template type: {template_type}. Must be 'system' or 'action'.", err=True)
                raise typer.Exit(code=1)
        
        # Check if template exists
        if not template_path.exists():
            typer.echo(f"Template {template_path} not found.", err=True)
            raise typer.Exit(code=1)
        
        # Check for default templates
        if template_path.name in ["system_role.jinja", "reasoning.jinja", "stub.jinja", "strategic.jinja"]:
            typer.echo(f"Cannot delete default template: {template_path.name}", err=True)
            typer.echo("You can create a new template to override it instead.", err=True)
            raise typer.Exit(code=1)
        
        # Confirm deletion
        if not force and not typer.confirm(f"Are you sure you want to delete template {template_path}?"):
            typer.echo("Template deletion cancelled.")
            return
        
        # Delete template
        template_path.unlink()
        typer.echo(f"Template {template_path} deleted successfully.")
                
    except Exception as e:
        log.exception(f"Error deleting template: {e}")
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()