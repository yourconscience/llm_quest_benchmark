"""CLI commands for llm-quest-benchmark"""
import logging
import click
from pathlib import Path
from typing import Optional, List

import typer

from llm_quest_benchmark.core.logging import LogManager
from llm_quest_benchmark.core.runner import run_quest_with_timeout, QuestRunner
from llm_quest_benchmark.core.analyzer import analyze_quest_run
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.executors.benchmark import run_benchmark, print_summary
from llm_quest_benchmark.constants import (
    MODEL_CHOICES,
    DEFAULT_MODEL,
    DEFAULT_QUEST,
    DEFAULT_TEMPLATE,
    REASONING_TEMPLATE,
    DEFAULT_TEMPERATURE,
)
from llm_quest_benchmark.executors.benchmark_config import BenchmarkConfig, AgentConfig
from llm_quest_benchmark.executors.qm_player import play_quest
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
    debug: bool = typer.Option(False, help="Enable debug logging and output."),
    model: str = typer.Option(DEFAULT_MODEL, help=f"Model for the LLM agent (choices: {', '.join(MODEL_CHOICES)})."),
    headless: bool = typer.Option(False, help="Run without terminal UI, output clean logs only."),
    timeout_seconds: int = typer.Option(60, help="Timeout in seconds (0 for no timeout)."),
    template: str = typer.Option(DEFAULT_TEMPLATE, help=f"Template to use for action prompts (default: {DEFAULT_TEMPLATE}, reasoning: {REASONING_TEMPLATE})."),
    skip: bool = typer.Option(False, help="Auto-select single choices without asking agent."),
    temperature: float = typer.Option(DEFAULT_TEMPERATURE, help="Temperature for LLM sampling"),
):
    """Run a quest with an LLM agent.

    This command runs a Space Rangers quest using an LLM agent. The agent will attempt to complete
    the quest by making decisions based on the quest text and available choices.

    Example:
        llm-quest run --quest quests/boat.qm --model sonnet --debug
    """
    try:
        log_manager.setup(debug)
        log.info(f"Starting quest run with model {model}")
        log.debug(f"Quest file: {quest}")
        log.debug(f"Timeout: {timeout_seconds}s")
        log.debug(f"Using template: {template}")

        # Run quest with timeout if specified
        if timeout_seconds > 0:
            result = run_quest_with_timeout(
                quest_path=str(quest),
                model=model,
                debug=debug,
                headless=headless,
                template=template,
                skip_single=skip,
                temperature=temperature,
                timeout_seconds=timeout_seconds
            )
        else:
            # Run without timeout
            runner = QuestRunner(headless=headless)
            runner.initialize(
                quest=str(quest),
                model=model,
                debug=debug,
                headless=headless,
                template=template,
                skip_single=skip,
                temperature=temperature,
            )
            outcome = runner.run()
            result = {
                'outcome': outcome.name,
                'error': None
            }

        # Handle outcome
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
        outcome = play_quest(
            quest=str(quest),
            player=player,
            skip_single=skip,
            debug=debug
        )

        _handle_quest_outcome(outcome, "Quest play")

    except typer.Exit:
        raise  # Re-raise typer.Exit without logging
    except Exception as e:
        log.exception(f"Error during interactive play: {e}")
        raise typer.Exit(code=2)

@app.command()
def analyze(
    metrics_file: Optional[Path] = typer.Option(None, help="Path to the metrics JSON file. If not provided, uses most recent file."),
    debug: bool = typer.Option(False, help="Enable debug logging and output."),
):
    """Analyze metrics from a quest run.

    This command analyzes the metrics collected during a quest run, showing summary statistics
    and step-by-step decision analysis. If no metrics file is specified, it uses the most recent one.

    Example:
        llm-quest analyze
        llm-quest analyze --metrics-file metrics/quest_run_20250217_144717.jsonl --debug
    """
    try:
        results = analyze_quest_run(metrics_file, debug)

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
        log.info(f"Timeout: {benchmark_config.timeout_seconds}s")
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
def test(
    quest: Path = typer.Option(DEFAULT_QUEST, help="Path to the QM quest file."),
    debug: bool = typer.Option(False, help="Enable debug logging and output."),
    model: str = typer.Option(DEFAULT_MODEL, help=f"Model for the LLM agent (choices: {', '.join(MODEL_CHOICES)})."),
    template: str = typer.Option(DEFAULT_TEMPLATE, help=f"Template to use for action prompts (default: {DEFAULT_TEMPLATE}, reasoning: {REASONING_TEMPLATE})."),
):
    """Test a quest with specified agent (headless)"""
    try:
        log_manager.setup(debug)
        log.info(f"Testing quest {quest} with model {model}")

        result = run_quest_with_timeout(
            quest_path=str(quest),
            model=model,
            debug=debug,
            headless=True,
            template=template,
            timeout_seconds=60  # Use default timeout for tests
        )

        outcome = QuestOutcome[result['outcome']]
        _handle_quest_outcome(outcome, "Quest test")

    except typer.Exit:
        raise
    except Exception as e:
        log.exception(f"Error during quest test: {e}")
        raise typer.Exit(code=2)

if __name__ == "__main__":
    app()