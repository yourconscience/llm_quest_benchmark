"""CLI commands for llm-quest-benchmark"""
from pathlib import Path
from typing import Optional

import typer
from typing_extensions import Annotated

from llm_quest_benchmark.core.logger import LogManager
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
)

# Initialize logging
log_manager = LogManager()
log = log_manager.get_logger()

app = typer.Typer(
    help="llm-quest: Command-line tools for LLM Quest Benchmark.",
    rich_markup_mode="rich",
)

@app.command(help="Run a quest with an LLM agent.")
def run(
    quest: Annotated[
        Path,
        typer.Option(
            ...,
            "--quest",
            "-q",
            help="Path to the QM quest file.",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    log_level: Annotated[
        str,
        typer.Option(
            "--log-level",
            "-l",
            help="Logging level (debug, info, warning, error).",
        ),
    ] = "info",
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help=f"Model for the LLM agent (choices: {', '.join(MODEL_CHOICES)}).",
        ),
    ] = DEFAULT_MODEL,
    language: Annotated[
        str,
        typer.Option(
            "--language",
            "--lang",
            "-l",
            help=f"Language for quest text (choices: {', '.join(LANG_CHOICES)}).",
        ),
    ] = DEFAULT_LANG,
    metrics: Annotated[
        bool,
        typer.Option(
            "--metrics",
            help="Enable automatic metrics logging to metrics/ directory.",
        ),
    ] = False,
    headless: Annotated[
        bool,
        typer.Option(
            "--headless",
            help="Run without terminal UI, output clean logs only.",
        ),
    ] = False,
    timeout_seconds: Annotated[
        int,
        typer.Option(
            "--timeout",
            "-t",
            help="Timeout in seconds (0 for no timeout).",
        ),
    ] = 60,
):
    """Run a quest with an LLM agent."""
    try:
        log_manager.setup(log_level)
        log.info(f"Starting quest run with model {model}")
        log.debug(f"Quest file: {quest}")
        log.debug(f"Timeout: {timeout_seconds}s")

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

@app.command(help="Play a quest interactively in the console.")
def play(
    quest: Annotated[
        Path,
        typer.Option(
            ...,
            "--quest",
            "-q",
            help="Path to the QM quest file.",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    language: Annotated[
        str,
        typer.Option(
            "--language",
            "--lang",
            "-l",
            help=f"Language for quest text (choices: {', '.join(LANG_CHOICES)}).",
        ),
    ] = DEFAULT_LANG,
    skip: Annotated[
        bool,
        typer.Option(
            "--skip",
            "-s",
            help="Automatically select screens with only one available option.",
        ),
    ] = False,
    metrics: Annotated[
        bool,
        typer.Option(
            "--metrics",
            "-m",
            help="Enable automatic metrics logging to metrics/ directory.",
        ),
    ] = False,
    log_level: Annotated[
        str,
        typer.Option(
            "--log-level",
            "-l",
            help="Logging level (debug, info, warning, error).",
        ),
    ] = "info",
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

@app.command(help="Analyze metrics from a quest run.")
def analyze(
    metrics_file: Annotated[
        Path,
        typer.Option(
            ...,
            "--metrics-file",
            "-m",
            help="Path to the metrics JSON file.",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    log_level: Annotated[
        str,
        typer.Option(
            "--log-level",
            "-l",
            help="Logging level (debug, info, warning, error).",
        ),
    ] = "info",
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