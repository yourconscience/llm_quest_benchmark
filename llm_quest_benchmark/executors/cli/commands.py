"""CLI commands for llm-quest-benchmark"""
from pathlib import Path
from typing import Optional

import typer

from llm_quest_benchmark.core.logging import LogManager
from llm_quest_benchmark.core.time import timeout, CommandTimeout
from llm_quest_benchmark.core.runner import run_quest
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.executors.qm_player import play_quest
from llm_quest_benchmark.constants import (
    MODEL_CHOICES,
    DEFAULT_MODEL,
    LANG_CHOICES,
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
    """
    pass

@app.command()
def run(
    quest: Path = typer.Option(DEFAULT_QUEST, help="Path to the QM quest file."),
    log_level: str = typer.Option("info", help="Logging level (debug, info, warning, error)."),
    model: str = typer.Option(DEFAULT_MODEL, help=f"Model for the LLM agent (choices: {', '.join(MODEL_CHOICES)})."),
    language: str = typer.Option(DEFAULT_LANG, help=f"Language for quest text (choices: {', '.join(LANG_CHOICES)})."),
    metrics: bool = typer.Option(False, help="Enable automatic metrics logging to metrics/ directory."),
    headless: bool = typer.Option(False, help="Run without terminal UI, output clean logs only."),
    timeout_seconds: int = typer.Option(60, help="Timeout in seconds (0 for no timeout)."),
    template: str = typer.Option(DEFAULT_TEMPLATE, help=f"Template to use for action prompts (default: {DEFAULT_TEMPLATE}, reasoning: {REASONING_TEMPLATE})."),
):
    """Run a quest with an LLM agent."""
    try:
        log_manager.setup(log_level)
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
                        language=language,
                        log_level=log_level,
                        metrics=metrics,
                        headless=headless,
                        template=template,
                    )
            except CommandTimeout:
                outcome = QuestOutcome.ERROR
        else:
            outcome = run_quest(
                quest=str(quest),
                model=model,
                language=language,
                log_level=log_level,
                metrics=metrics,
                headless=headless,
                template=template,
            )

        # Map outcome to exit code
        exit_codes = {
            QuestOutcome.SUCCESS: 0,
            QuestOutcome.FAILURE: 1,
            QuestOutcome.ERROR: 2
        }

        log.info(f"Quest run completed with outcome: {outcome}")
        raise typer.Exit(code=exit_codes[outcome])

    except Exception as e:
        log.exception(f"Error during quest run: {e}")
        raise typer.Exit(code=2)

@app.command()
def play(
    quest: Path = typer.Option(DEFAULT_QUEST, help="Path to the QM quest file."),
    language: str = typer.Option(DEFAULT_LANG, help=f"Language for quest text (choices: {', '.join(LANG_CHOICES)})."),
    skip: bool = typer.Option(False, help="Automatically select screens with only one available option."),
    metrics: bool = typer.Option(False, help="Enable automatic metrics logging to metrics/ directory."),
    log_level: str = typer.Option("info", help="Logging level (debug, info, warning, error)."),
):
    """Play a Space Rangers quest interactively."""
    try:
        log_manager.setup(log_level)
        log.info(f"Starting interactive quest play")
        log.debug(f"Quest file: {quest}")

        outcome = play_quest(
            quest=str(quest),
            language=language,
            log_level=log_level,
            skip_single=skip,
            metrics=metrics,
        )

        # Map outcome to exit code
        exit_codes = {
            QuestOutcome.SUCCESS: 0,
            QuestOutcome.FAILURE: 1,
            QuestOutcome.ERROR: 2
        }

        log.info(f"Quest play completed with outcome: {outcome}")
        raise typer.Exit(code=exit_codes[outcome])

    except Exception as e:
        log.exception(f"Error during interactive play: {e}")
        raise typer.Exit(code=2)

@app.command()
def analyze(
    metrics_file: Path = typer.Option(..., help="Path to the metrics JSON file."),
    log_level: str = typer.Option("info", help="Logging level (debug, info, warning, error)."),
):
    """Analyze metrics from a quest run."""
    try:
        log_manager.setup(log_level)
        log.info(f"Analyzing metrics from {metrics_file}")

        import json
        with open(str(metrics_file), "r") as f:
            metrics = json.load(f)
        typer.echo(json.dumps(metrics, indent=2))
    except Exception as e:
        log.exception(f"Error analyzing metrics: {e}")
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()