"""Unified CLI entry point for llm-quest-benchmark"""
from pathlib import Path
from typing import Optional

import typer
from typing_extensions import Annotated

from llm_quest_benchmark.scripts.qm_player import play_quest as play_quest_func
from llm_quest_benchmark.scripts.run_quest import run_quest as run_quest_func
from llm_quest_benchmark.constants import MODEL_CHOICES

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
    output: Annotated[
        Optional[Path],
        typer.Option(
            "--output",
            "-o",
            help="Path to save metrics JSON file.",
            file_okay=True,
            dir_okay=False,
            writable=True,
        ),
    ] = None,
    model: Annotated[
        str,
        typer.Option(
            "--model",
            "-m",
            help="Model for the LLM agent.",
        ),
    ] = None,
):
    exit_code = run_quest_func(str(quest), log_level, output, model)
    raise typer.Exit(code=exit_code)


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
):
    analyze_metrics_func(str(metrics_file))


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
            help="Language for quest text (rus, eng).",
        ),
    ] = "rus",
):
    play_quest_func(str(quest), language)


if __name__ == "__main__":
    app()
    app()