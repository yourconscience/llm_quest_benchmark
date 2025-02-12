"""CLI commands for llm-quest-benchmark"""
import os
import logging
import signal
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.logging import RichHandler
from typing_extensions import Annotated

from llm_quest_benchmark.executors.qm_player import play_quest as play_quest_func
from llm_quest_benchmark.runner import run_quest as run_quest_func
from llm_quest_benchmark.constants import (
    MODEL_CHOICES,
    DEFAULT_MODEL,
    LANG_CHOICES,
    DEFAULT_LANG,
)

# Set up logging with rich handler
logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)]
)
log = logging.getLogger("llm-quest")

# Set transformers logging level
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

class CommandTimeout(Exception):
    """Raised when a command times out"""
    pass

@contextmanager
def timeout(seconds: int):
    """Context manager for timing out long-running operations"""
    def handler(signum, frame):
        raise CommandTimeout(f"Operation timed out after {seconds} seconds")

    # Register a function to raise the timeout error when signal received
    signal.signal(signal.SIGALRM, handler)
    signal.alarm(seconds)

    try:
        yield
    finally:
        # Disable the alarm
        signal.alarm(0)

app = typer.Typer(
    help="llm-quest: Command-line tools for LLM Quest Benchmark.",
    rich_markup_mode="rich",
)

def setup_logging(log_level: str) -> None:
    """Configure logging based on the specified level"""
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")

    log.setLevel(numeric_level)
    if log_level.upper() == "DEBUG":
        # Create logs directory if it doesn't exist
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        # Add file handler for debug logging
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_handler = logging.FileHandler(log_dir / f"llm_quest_{timestamp}.log")
        debug_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        debug_handler.setFormatter(formatter)
        log.addHandler(debug_handler)
        log.debug("Debug logging enabled")

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
        setup_logging(log_level)
        log.info(f"Starting quest run with model {model}")
        log.debug(f"Quest file: {quest}")
        log.debug(f"Timeout: {timeout_seconds}s")

        if timeout_seconds > 0:
            with timeout(timeout_seconds):
                exit_code = run_quest_func(
                    quest=str(quest),
                    log_level=log_level,
                    model=model,
                    metrics=metrics,
                )
        else:
            exit_code = run_quest_func(
                quest=str(quest),
                log_level=log_level,
                model=model,
                metrics=metrics,
            )

        log.info("Quest run completed")
        raise typer.Exit(code=exit_code)

    except CommandTimeout as e:
        log.error(f"Timeout error: {e}")
        raise typer.Exit(code=1)
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
        setup_logging(log_level)
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
        setup_logging(log_level)
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