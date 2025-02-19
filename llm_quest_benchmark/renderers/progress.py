"""Progress bar renderer for benchmark runs using tqdm"""
from typing import Dict, List, Optional, Any
from tqdm import tqdm
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.renderers.base import BaseRenderer


class ProgressRenderer(BaseRenderer):
    """Renders benchmark progress with tqdm and rich"""

    def __init__(self, total_quests: int, total_runs: int):
        """Initialize progress renderer

        Args:
            total_quests (int): Total number of quests to run
            total_runs (int): Total number of quest runs (quests * agents)
        """
        self.console = Console()
        self.total_quests = total_quests
        self.total_runs = total_runs

        # Initialize counters
        self.success_count = 0
        self.failure_count = 0
        self.error_count = 0
        self.timeout_count = 0

        # Create progress bar
        self.progress = tqdm(
            total=total_runs,
            desc="Running benchmark",
            unit="run",
            ncols=100,
            bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]"
        )

        # Print initial header
        self.console.print("\n[bold cyan]Benchmark Progress[/]")
        self.console.print("=" * 80)

    def render_game_state(self, state: Dict[str, Any]) -> None:
        """Minimal game state rendering for automated agents - no visual output needed"""
        pass

    def render_title(self) -> None:
        """No title rendering needed for automated agents"""
        pass

    def render_quest_text(self, text: str) -> None:
        """No quest text rendering needed for automated agents"""
        pass

    def render_choices(self, choices: list) -> None:
        """No choices rendering needed for automated agents"""
        pass

    def render_parameters(self, params: list) -> None:
        """No parameters rendering needed for automated agents"""
        pass

    def render_error(self, message: str) -> None:
        """Render error in progress output"""
        self.console.print(f"[red]Error: {message}[/]")

    def update(self, quest_name: str, model: str, outcome: QuestOutcome, error: Optional[str] = None) -> None:
        """Update progress with latest quest run result

        Args:
            quest_name (str): Name of the quest
            model (str): Name of the model/agent
            outcome (QuestOutcome): Outcome of the quest run
            error (Optional[str]): Error message if any
        """
        # Update counters
        if outcome == QuestOutcome.SUCCESS:
            self.success_count += 1
        elif outcome == QuestOutcome.FAILURE:
            self.failure_count += 1
        elif outcome == QuestOutcome.TIMEOUT:
            self.timeout_count += 1
        elif outcome == QuestOutcome.ERROR:
            self.error_count += 1

        # Update progress description with stats
        stats = f"[S:{self.success_count}|F:{self.failure_count}|E:{self.error_count}|T:{self.timeout_count}]"
        self.progress.set_description(f"Running benchmark {stats}")

        # Update progress bar
        self.progress.update(1)

        # Print run result with color
        status_color = {
            QuestOutcome.SUCCESS: "green",
            QuestOutcome.FAILURE: "yellow",
            QuestOutcome.ERROR: "red",
            QuestOutcome.TIMEOUT: "red"
        }.get(outcome, "white")

        self.console.print(
            f"[{status_color}]{quest_name} - {model}: {outcome.name}[/]" +
            (f" ({error})" if error else "")
        )

    def close(self) -> None:
        """Close progress bars and display final summary"""
        self.progress.close()

        # Create summary table
        table = Table(title="Benchmark Summary", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Count", justify="right", style="green")
        table.add_column("Percentage", justify="right", style="blue")

        total = self.total_runs
        table.add_row(
            "Success",
            str(self.success_count),
            f"{(self.success_count/total)*100:.1f}%"
        )
        table.add_row(
            "Failure",
            str(self.failure_count),
            f"{(self.failure_count/total)*100:.1f}%"
        )
        table.add_row(
            "Error",
            str(self.error_count),
            f"{(self.error_count/total)*100:.1f}%"
        )
        table.add_row(
            "Timeout",
            str(self.timeout_count),
            f"{(self.timeout_count/total)*100:.1f}%"
        )
        table.add_row(
            "Total",
            str(total),
            "100%"
        )

        self.console.print("\n")
        self.console.print(Panel(table, expand=False))