"""Renderer for benchmark results analysis"""
from typing import Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

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

    def render_game_state(self, state: Optional[Dict[str, Any]] = None) -> None:
        """Required implementation of abstract method from BaseRenderer.
        Not used in benchmark analysis but required by the interface.

        Args:
            state: Game state dictionary (unused)
        """
        pass  # Not used for benchmark analysis

    def render_config(self, config: Dict[str, Any]) -> None:
        """Render benchmark configuration

        Args:
            config: Benchmark configuration dictionary
        """
        self.console.print("\n[bold cyan]Benchmark Configuration[/]")
        self.console.print("=" * 80)
        table = Table(show_header=False, box=None)
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Quest Timeout", f"{config['quest_timeout']}s")
        table.add_row("Benchmark Timeout", f"{config['benchmark_timeout']}s")
        table.add_row("Debug Mode", str(config['debug']))
        table.add_row("Max Workers", str(config['max_workers']))

        self.console.print(table)

    def render_agents(self, agents: list) -> None:
        """Render agent configurations

        Args:
            agents: List of agent configuration dictionaries
        """
        self.console.print("\n[bold cyan]Agent Configurations[/]")
        self.console.print("=" * 80)

        for agent in agents:
            table = Table(show_header=False, box=None)
            table.add_column("Setting", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Model", agent['model'])
            table.add_row("Template", agent['template'])
            table.add_row("Temperature", str(agent['temperature']))
            table.add_row("Skip Single", str(agent.get('skip_single', False)))

            self.console.print(table)
            self.console.print()

    def render_summary(self, summary: Dict[str, Any], quests: list) -> None:
        """Render overall benchmark summary

        Args:
            summary: Benchmark summary dictionary
            quests: List of quest results
        """
        self.console.print("\n[bold cyan]Overall Results[/]")
        self.console.print("=" * 80)

        # Calculate step statistics
        total_steps = summary.get('total_steps', 0)
        failure_steps = summary.get('failure_steps', 0)
        avg_steps_per_failure = failure_steps / summary['outcomes'].get('FAILURE', 1) if summary['outcomes'].get('FAILURE') else 0

        # Print quest names first
        self.console.print("\n[bold]Quests tested:[/]")
        for quest in quests:
            self.console.print(f"- {quest['name']}")

        # Results table
        table = Table(show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Count", justify="right", style="green")
        table.add_column("Percentage", justify="right", style="blue")
        table.add_column("Steps", justify="right", style="magenta")

        total_runs = summary['total_runs']
        for outcome, count in summary['outcomes'].items():
            percentage = (count / total_runs) * 100
            step_info = f"Ø{avg_steps_per_failure:.1f}" if outcome == 'FAILURE' else "-"
            table.add_row(
                outcome,
                str(count),
                f"{percentage:.1f}%",
                step_info
            )

        table.add_row("Total Quests", str(summary['total_quests']), "", "")
        table.add_row("Total Runs", str(total_runs), "100%", str(total_steps))

        self.console.print(Panel(table, expand=False))

    def render_step(self, step: Dict[str, Any]) -> None:
        """Render a single step with full details

        Args:
            step: Step information dictionary
        """
        self.console.print(f"\n[bold]Step {step.get('step', '?')}:[/]")

        # Print full state text
        if step.get('state'):
            self.console.print(Text(step['state'], style="blue"))

        # Print choices without duplication
        if step.get('choices'):
            self.console.print("\n[bold]Available actions:[/]")
            for choice in step['choices']:
                self.console.print(f"  {choice['id']}: {choice['text']}")

        # Print selected action
        if step.get('action'):
            self.console.print(f"\n[bold]Selected:[/] {step['action']}")

        # Print LLM response details if available
        if step.get('llm_response'):
            self.console.print(f"\n[bold]LLM Response:[/] {step['llm_response']}")
        if step.get('reasoning'):
            self.console.print(f"\n[bold]Reasoning:[/] {step['reasoning']}")
        if step.get('analysis'):
            self.console.print(f"\n[bold]Analysis:[/] {step['analysis']}")

    def render_quest_details(self, quest: Dict[str, Any], debug: bool = False) -> None:
        """Render detailed results for a single quest

        Args:
            quest: Quest results dictionary
            debug: Whether to show debug information
        """
        self.console.print(f"\n[bold]{quest['name']}[/]")
        self.console.print("-" * 40)

        # Quest summary table
        table = Table(show_header=True, box=None)
        table.add_column("Outcome", style="cyan")
        table.add_column("Count", justify="right", style="green")
        table.add_column("Percentage", justify="right", style="blue")

        for outcome, count in quest['outcomes'].items():
            percentage = (count / quest['total_runs']) * 100
            table.add_row(
                outcome,
                str(count),
                f"{percentage:.1f}%"
            )

        self.console.print(table)

        if debug:
            # Detailed run information
            for result in quest['results']:
                self.console.print(f"\n[dim]Run with {result['model']} (temp={result['temperature']})[/]")
                self.console.print(f"Outcome: {result['outcome']}")

                if result.get('error'):
                    self.console.print(Text(f"Error: {result['error']}", style="red"))

                # Show steps if available
                for step in result.get('steps', []):
                    self.render_step(step)

    def render_benchmark_results(self, data: Dict[str, Any], debug: bool = False) -> None:
        """Render complete benchmark results

        Args:
            data: Complete benchmark data dictionary
            debug: Whether to show debug information
        """
        # Render sections
        self.render_config(data['config'])
        self.render_agents(data['agents'])
        self.render_summary(data['summary'], data['quests'])

        # Quest details
        self.console.print("\n[bold cyan]Quest Details[/]")
        self.console.print("=" * 80)

        for quest in data['quests']:
            self.render_quest_details(quest, debug)