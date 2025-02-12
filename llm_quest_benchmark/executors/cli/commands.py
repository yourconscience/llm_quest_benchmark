"""CLI commands for llm-quest-benchmark"""
from pathlib import Path
from typing import Optional

import typer
from typing_extensions import Annotated

from llm_quest_benchmark.core.logger import LogManager
from llm_quest_benchmark.core.time import timeout, CommandTimeout
from llm_quest_benchmark.core.runner import run_quest as run_quest_func
from llm_quest_benchmark.executors.qm_player import play_quest as play_quest_func
from llm_quest_benchmark.constants import (
    MODEL_CHOICES,
    DEFAULT_MODEL,
    LANG_CHOICES,
    DEFAULT_LANG,
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
    metrics: Annotated[
        bool,
        typer.Option(
            "--metrics",
            help="Enable automatic metrics logging to metrics/ directory.",
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
                    exit_code = run_quest_func(
                        quest=str(quest),
                        log_level=log_level,
                        model=model,
                        metrics=metrics,
                        logger=log,
                    )
            except CommandTimeout as e:
                if log_level.upper() == "DEBUG":
                    log.error(
                        f"Timeout error: {e}\n"
                        "Debug suggestions:\n"
                        "1. Check if the model API is responding\n"
                        "2. Consider increasing timeout with --timeout option\n"
                        "3. Check logs for any errors before timeout\n"
                        "4. Try running with --model sonnet for faster responses"
                    )
                else:
                    log.error(f"Timeout error: {e}")
                raise typer.Exit(code=1)
        else:
            exit_code = run_quest_func(
                quest=str(quest),
                log_level=log_level,
                model=model,
                metrics=metrics,
                logger=log,
            )

        log.info("Quest run completed")
        raise typer.Exit(code=exit_code)

    except Exception as e:
        log.exception(f"Error during quest run: {e}")
        raise typer.Exit(code=1)

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

        play_quest_func(
            quest_path=str(quest),
            language=language,
            skip=skip,
            metrics=metrics,
        )
    except Exception as e:
        log.exception(f"Error during interactive play: {e}")
        raise typer.Exit(code=1)

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