"""CLI commands for llm-quest-benchmark"""
from pathlib import Path
from typing import Optional

import typer

from llm_quest_benchmark.core.logging import LogManager
from llm_quest_benchmark.core.time import timeout, CommandTimeout
from llm_quest_benchmark.core.runner import run_quest
from llm_quest_benchmark.core.analyzer import analyze_quest_run
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.executors.qm_player import play_quest
from llm_quest_benchmark.constants import (
    MODEL_CHOICES,
    DEFAULT_MODEL,
    DEFAULT_LANG,
    DEFAULT_QUEST,
    DEFAULT_TEMPLATE,
    REASONING_TEMPLATE,
)

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
    if outcome.exit_code == 0:
        raise typer.Exit(code=outcome.exit_code)
    else:
        log.error(f"Quest failed with error code: {outcome.exit_code}")
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

        if timeout_seconds > 0:
            try:
                with timeout(timeout_seconds):
                    outcome = run_quest(
                        quest=str(quest),
                        model=model,
                        language=DEFAULT_LANG,
                        debug=debug,
                        headless=headless,
                        template=template,
                    )
            except CommandTimeout:
                outcome = QuestOutcome.ERROR
        else:
            outcome = run_quest(
                quest=str(quest),
                model=model,
                language=DEFAULT_LANG,
                debug=debug,
                headless=headless,
                template=template,
            )

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

        outcome = play_quest(
            quest=str(quest),
            skip_single=skip,
            debug=debug,
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

if __name__ == "__main__":
    app()