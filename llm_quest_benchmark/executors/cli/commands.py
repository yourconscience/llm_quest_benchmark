"""CLI commands for llm-quest-benchmark"""
import logging
import click
from pathlib import Path
from typing import Optional, List
import socket

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
from llm_quest_benchmark.dataclasses.config import AgentConfig, BenchmarkConfig
from llm_quest_benchmark.agents.human_player import HumanPlayer
from llm_quest_benchmark.web.app import create_app

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
    db: Path = typer.Option("metrics.db", help="Path to SQLite database."),
    debug: bool = typer.Option(False, help="Enable debug logging and output."),
):
    """Analyze metrics from quest runs or benchmark results.

    This command analyzes metrics from the SQLite database, showing summary statistics and detailed analysis.
    You can either analyze a specific quest (using --quest) or a benchmark (using --benchmark).

    Example:
        llm-quest analyze --benchmark baseline  # Analyze baseline benchmark results
        llm-quest analyze --quest boat.qm  # Analyze specific quest
        llm-quest analyze --quest boat.qm --db custom.db  # Use custom database
    """
    try:
        # Validate input - must specify either quest or benchmark
        if not quest and not benchmark:
            typer.echo("Must specify either --quest or --benchmark.", err=True)
            raise typer.Exit(code=1)
        if quest and benchmark:
            typer.echo("Cannot specify both --quest and --benchmark. Please choose one.", err=True)
            raise typer.Exit(code=1)

        # Validate database exists
        if not db.exists():
            typer.echo(f"Database not found: {db}", err=True)
            raise typer.Exit(code=1)

        # Analyze quest run
        if quest:
            results = analyze_quest_run(quest, db, debug)

            # Print human-readable summary
            typer.echo("\nQuest Run Summary")
            typer.echo("================")
            typer.echo(f"Quest: {results['quest_name']}")
            typer.echo(f"Total Runs: {results['total_runs']}")
            for outcome, count in results['outcomes'].items():
                typer.echo(f"{outcome}: {count}")

            # Print run details
            for run in results['runs']:
                typer.echo(f"\nRun at {run['start_time']}")
                typer.echo(f"Model: {run['model']}")
                typer.echo(f"Template: {run['template']}")
                typer.echo(f"Outcome: {run['outcome']}")
                typer.echo(f"Reward: {run['reward']}")

                if debug and run['steps']:
                    typer.echo("\nSteps:")
                    for step in run['steps']:
                        typer.echo(f"\nStep {step['step']}:")
                        typer.echo(f"Observation: {step['observation']}")
                        typer.echo("Choices:")
                        for choice in step['choices']:
                            typer.echo(f"  {choice['id']}: {choice['text']}")
                        typer.echo(f"Action: {step['action']}")
                        typer.echo(f"Reward: {step['reward']}")
                        if step.get('llm_response'):
                            typer.echo(f"LLM Response: {step['llm_response']}")

        # Analyze benchmark results
        else:
            analyze_benchmark(db, benchmark, debug)

    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        log.exception(f"Error during analysis: {e}")
        raise typer.Exit(code=1)

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
        log.info(f"Workers: {benchmark_config.max_workers}")
        log.info(f"Output directory: {benchmark_config.output_dir}")

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

if __name__ == "__main__":
    app()