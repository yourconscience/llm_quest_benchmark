"""Renderer for benchmark results analysis"""

from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from llm_quest_benchmark.renderers.base import BaseRenderer


class BenchmarkResultRenderer(BaseRenderer):
    """Renders benchmark results analysis with rich formatting"""

    def __init__(self, debug: bool = False):
        """Initialize the renderer

        Args:
            debug: Enable debug output
        """
        self.debug = debug
        self.console = Console()

    def render_game_state(self, transition: Any = None) -> None:
        """Required implementation of abstract method from BaseRenderer.
        Not used in benchmark analysis but required by the interface.

        Args:
            transition: Executed transition (unused)
        """
        pass  # Not used for benchmark analysis

    def render_benchmark_results(self, data: dict[str, Any], debug: bool = False) -> None:
        """Render complete benchmark results

        Args:
            data: Complete benchmark data dictionary
            debug: Whether to show debug information
        """
        # Print overall summary
        self.console.print("\n[bold cyan]Benchmark Results[/]")
        self.console.print("=" * 80)

        # Print benchmark id if available
        if "benchmark_id" in data:
            self.console.print(f"\nBenchmark: {data['benchmark_id']}")

        # Overall statistics
        summary = data["summary"]
        self.console.print(f"\nTotal Runs: {summary['total_runs']}")
        self.console.print(f"Success Rate: {summary['success_rate']:.1f}%")
        self.console.print(f"Average Success Reward: {summary['avg_success_reward']:.2f}")

        # Outcome table
        outcome_table = Table(title="Outcome Summary", box=box.ROUNDED)
        outcome_table.add_column("Outcome", style="cyan")
        outcome_table.add_column("Count", style="magenta")
        outcome_table.add_column("Percentage", style="green")

        total = summary["total_runs"]
        for outcome, count in summary["outcomes"].items():
            outcome_table.add_row(outcome, str(count), f"{count / total * 100:.1f}%" if total else "0%")

        self.console.print(Panel(outcome_table, title="Outcomes", expand=False))

        # Model statistics
        model_table = Table(title="Model Performance", box=box.ROUNDED)
        model_table.add_column("Model", style="cyan")
        model_table.add_column("Runs", style="magenta")
        model_table.add_column("Success Rate", style="green")
        model_table.add_column("Avg Reward", style="blue")

        for model in data["models"]:
            model_table.add_row(
                model["name"], str(model["runs"]), f"{model['success_rate']:.1f}%", f"{model['avg_reward']:.2f}"
            )

        self.console.print(Panel(model_table, title="Model Statistics", expand=False))

        # Quest statistics
        quest_table = Table(title="Quest Results", box=box.ROUNDED)
        quest_table.add_column("Quest", style="cyan")
        quest_table.add_column("Runs", style="magenta")
        quest_table.add_column("Success Rate", style="green")

        for quest in data["quests"]:
            quest_table.add_row(quest["name"], str(quest["runs"]), f"{quest['success_rate']:.1f}%")

        self.console.print(Panel(quest_table, title="Quest Statistics", expand=False))

        # Treatment statistics, grouped by canonical signature and components.
        # Printed as one short line per component instead of a wide table: a
        # seven-column table is narrower than its content on an 80-column
        # terminal, so rich would silently truncate names such as the harness.
        if data.get("treatments"):
            self.console.print("\n[bold cyan]Treatment Statistics[/]")
            self.console.print("=" * 80)
            for treatment in data["treatments"]:
                self.console.print(f"\nSignature: {treatment['signature']}")
                for component in ("harness", "memory", "loop", "reasoning"):
                    self.console.print(f"  {component}: {treatment[component]}")
                self.console.print(f"  runs: {treatment['runs']}")
                self.console.print(f"  success rate: {treatment['success_rate']:.1f}%")
