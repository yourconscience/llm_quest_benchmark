"""CLI commands for llm-quest-benchmark"""
import logging
import click
from pathlib import Path
from typing import Optional, List

from llm_quest_benchmark.agents.agent_factory import create_agent
import typer

from llm_quest_benchmark.core.logging import LogManager
from llm_quest_benchmark.core.runner import run_quest_with_timeout
from llm_quest_benchmark.core.analyzer import analyze_quest_run, analyze_benchmark
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.executors.benchmark import run_benchmark, print_summary
from llm_quest_benchmark.constants import (
    MODEL_CHOICES,
    DEFAULT_MODEL,
    DEFAULT_QUEST,
    DEFAULT_TEMPLATE,
    DEFAULT_TEMPERATURE,
    INFINITE_TIMEOUT,
)
from llm_quest_benchmark.dataclasses.config import AgentConfig, BenchmarkConfig
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

def _handle_quest_outcome(outcome: QuestOutcome, log_prefix: str) -> None:
    """Handle quest outcome and exit appropriately.

    Args:
        outcome: The quest outcome to handle
        log_prefix: Prefix for the log message (e.g. "Quest run" or "Quest play")
    """
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
    template: str = typer.Option(DEFAULT_TEMPLATE, help=f"Template to use for action prompts (default: {DEFAULT_TEMPLATE})."),
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
        agent = create_agent(model=model,
                             template=template,
                             temperature=temperature,
                             skip_single=skip,
                             debug=debug)

        log.warning(f"Starting quest run with agent {str(agent)}")
        log.debug(f"Quest file: {quest}")
        log.debug(f"Timeout: {timeout}s")

        timeout = timeout if timeout > 0 else 10**9
        result = run_quest_with_timeout(
                quest_path=str(quest),
                agent=agent,
                debug=debug,
                timeout=timeout
        )
        outcome = QuestOutcome[result['outcome']]
        _handle_quest_outcome(outcome, "Quest run")

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
        outcome = QuestOutcome[result['outcome']]
        _handle_quest_outcome(outcome, "Quest play")

    except typer.Exit:
        raise  # Re-raise typer.Exit without logging
    except Exception as e:
        log.exception(f"Error during interactive play: {e}")
        raise typer.Exit(code=2)

@app.command()
def analyze(
    quest: Optional[Path] = typer.Option(None, help="Path to a specific quest run metrics file (.jsonl) to analyze."),
    benchmark: Optional[Path] = typer.Option(None, help="Path to a benchmark directory or specific benchmark file (.json) to analyze. If not provided, uses the latest benchmark results."),
    debug: bool = typer.Option(False, help="Enable debug logging and output."),
):
    """Analyze metrics from benchmark runs or specific quest runs.

    This command analyzes metrics, showing summary statistics and detailed analysis.
    You can either analyze a specific quest run (using --quest) or benchmark results (using --benchmark).
    If neither is provided, it analyzes the latest benchmark results.

    Example:
        llm-quest analyze  # Analyze latest benchmark results
        llm-quest analyze --quest metrics/quest_run_20250217_144717.jsonl  # Analyze specific quest run
        llm-quest analyze --benchmark metrics/benchmarks/  # Analyze latest benchmark in directory
        llm-quest analyze --benchmark metrics/benchmarks/benchmark_20250217_144717.json  # Analyze specific benchmark
    """
    try:
        # Validate input - can't specify both
        if quest and benchmark:
            typer.echo("Cannot specify both --quest and --benchmark. Please choose one.", err=True)
            raise typer.Exit(code=1)

        # If quest file is provided, analyze as quest run
        if quest:
            if not quest.suffix == '.jsonl':
                typer.echo("Quest metrics file must be a .jsonl file", err=True)
                raise typer.Exit(code=1)

            results = analyze_quest_run(quest, debug)

            # Print human-readable summary
            typer.echo("\nQuest Run Summary")
            typer.echo("================")
            typer.echo(f"Quest File: {results['summary']['quest_file']}")
            typer.echo(f"Player Type: {results['summary']['player_type']}")
            if results['summary']['model']:
                typer.echo(f"Model: {results['summary']['model']}")
                typer.echo(f"Template: {results['summary']['template']}")
            typer.echo(f"Total Steps: {results['summary']['total_steps']}")
            typer.echo(f"Outcome: {results['summary']['outcome']}")

            # Print step summary
            typer.echo("\nStep Summary")
            typer.echo("============")
            for step in results['steps']:
                typer.echo(f"\nStep {step['step']}:")
                typer.echo(f"  Action: {step['action']}")
                typer.echo("  Available Choices:")
                for choice in step['choices']:
                    typer.echo(f"    {choice['id']}: {choice['text']}")
                if debug and step.get('state'):
                    typer.echo(f"  State: {step['state']}")
                    if step.get('prompt'):
                        typer.echo(f"  Prompt: {step['prompt']}")
                    if step.get('metrics'):
                        typer.echo(f"  Metrics: {step['metrics']}")
        else:
            # Handle benchmark analysis
            if benchmark:
                # If benchmark is a directory, find latest file in it
                if benchmark.is_dir():
                    files = list(benchmark.glob("benchmark_*.json"))
                    if not files:
                        typer.echo(f"No benchmark files found in directory: {benchmark}", err=True)
                        raise typer.Exit(code=1)
                    # Sort by modification time in descending order
                    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                    benchmark = files[0]
                elif not benchmark.suffix == '.json':
                    typer.echo("Benchmark file must be a .json file", err=True)
                    raise typer.Exit(code=1)

            # Analyze benchmark (will use latest if benchmark is None)
            analyze_benchmark(benchmark, debug)

    except ValueError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        log.exception(f"Error during analysis: {e}")
        raise typer.Exit(code=2)

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

if __name__ == "__main__":
    app()