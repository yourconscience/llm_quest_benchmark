"""CLI implementation for leaderboard functionality."""
import json
import logging
from pathlib import Path
from typing import List, Optional

import rich.table
import typer
from rich.console import Console

from llm_quest_benchmark.core.logging import LogManager
from llm_quest_benchmark.services.db_connectors import SQLiteConnector
from llm_quest_benchmark.services.leaderboard import LeaderboardService

# Initialize logger
log_manager = LogManager()
logger = log_manager.get_logger()
console = Console()


def display_leaderboard(
    db_path: Path,
    benchmark_id: Optional[str] = None,
    quest_type: Optional[str] = None,
    date_range: Optional[str] = None,
    agent_id: Optional[str] = None,
    memory_type: Optional[str] = None,
    tools: Optional[List[str]] = None,
    sort_by: str = "success_rate",
    sort_order: str = "desc",
    export: Optional[Path] = None,
    format: str = "table",
):
    """Display agent leaderboard in the CLI.

    Args:
        db_path: Path to SQLite database
        benchmark_id: Filter by benchmark ID
        quest_type: Filter by quest type
        date_range: Filter by date range (today, week, month)
        agent_id: Filter by agent ID
        memory_type: Filter by memory type (message_history, summary)
        tools: Filter by tools used
        sort_by: Field to sort by
        sort_order: Sort order (asc or desc)
        export: Path to export results
        format: Output format (table, json, compact)
    """
    # Create service with SQLite connector
    db_connector = SQLiteConnector(str(db_path))
    leaderboard_service = LeaderboardService(db_connector)

    # Get leaderboard entries
    entries = leaderboard_service.get_leaderboard_entries(
        benchmark_id=benchmark_id,
        quest_type=quest_type,
        date_range=date_range,
        agent_id=agent_id,
        memory_type=memory_type,
        tools=tools,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    # Export if requested
    if export:
        with open(export, 'w') as f:
            json.dump(entries, f, indent=2)
        typer.echo(f"Leaderboard exported to {export}")

    # Display results based on format
    if not entries:
        typer.echo("No results found")
        return

    if format == "json":
        typer.echo(json.dumps(entries, indent=2))
    elif format == "compact":
        for i, entry in enumerate(entries, 1):
            success_pct = entry['success_rate'] * 100
            typer.echo(f"{i}. {entry['agent_id']} | {entry['model']} | "
                       f"Success: {success_pct:.1f}% | Runs: {entry['runs_count']}")
    else:  # table format (default)
        # Create a rich table
        table = rich.table.Table(title="LLM Quest Benchmark Leaderboard")

        # Add columns
        table.add_column("Rank", justify="right", style="cyan")
        table.add_column("Agent", style="green")
        table.add_column("Model", style="blue")
        table.add_column("Success Rate", justify="right")
        table.add_column("Avg Reward", justify="right")
        table.add_column("Avg Steps", justify="right")
        table.add_column("Efficiency", justify="right")
        table.add_column("Memory", justify="center")
        table.add_column("Tools", justify="center")
        table.add_column("Runs", justify="right")

        # Add rows
        for i, entry in enumerate(entries, 1):
            # Format values
            success_pct = f"{entry['success_rate'] * 100:.1f}%"
            avg_reward = f"{entry['avg_reward']:.1f}"
            avg_steps = f"{entry['avg_steps']:.1f}"
            efficiency = f"{entry['efficiency_score']:.1f}"

            # Format memory type
            memory = entry.get('memory_type', 'none')

            # Format tools
            tools = ", ".join(entry.get('tools_used', [])) or "none"

            # Add to table
            table.add_row(
                str(i),
                entry['agent_id'],
                entry['model'],
                success_pct,
                avg_reward,
                avg_steps,
                efficiency,
                memory,
                tools,
                str(entry['runs_count']),
            )

        # Display the table
        console.print(table)


def display_agent_details(db_path: Path, agent_id: str, export: Optional[Path] = None):
    """Display detailed stats for a specific agent.

    Args:
        db_path: Path to SQLite database
        agent_id: Agent ID to display details for
        export: Path to export results
    """
    # Create service with SQLite connector
    db_connector = SQLiteConnector(str(db_path))
    leaderboard_service = LeaderboardService(db_connector)

    # Get agent details
    details = leaderboard_service.get_agent_detail(agent_id)

    # Export if requested
    if export:
        with open(export, 'w') as f:
            json.dump(details, f, indent=2)
        typer.echo(f"Agent details exported to {export}")

    # Display details
    if not details or not details.get('stats'):
        typer.echo(f"No data found for agent {agent_id}")
        return

    # Agent configuration section
    typer.echo(f"\n🤖 Agent: {agent_id}")
    typer.echo("=" * (len(agent_id) + 9))

    agent_config = details.get('agent_config', {})
    typer.echo(f"Model: {agent_config.get('model', 'unknown')}")
    typer.echo(f"Temperature: {agent_config.get('temperature', 'unknown')}")

    memory_config = agent_config.get('memory', {})
    if memory_config:
        typer.echo(f"Memory: {memory_config.get('type', 'none')} " +
                   f"(max history: {memory_config.get('max_history', 'unknown')})")
    else:
        typer.echo("Memory: none")

    tools = agent_config.get('tools', [])
    typer.echo(f"Tools: {', '.join(tools) if tools else 'none'}")

    # Performance stats section
    stats = details.get('stats', {})
    typer.echo("\n📊 Performance Stats")
    typer.echo("-----------------")
    typer.echo(f"Total Runs: {stats.get('total_runs', 0)}")
    typer.echo(f"Success Rate: {stats.get('success_rate', 0) * 100:.1f}%")
    typer.echo(f"Average Reward: {stats.get('avg_reward', 0):.1f}")
    typer.echo(f"Average Steps: {stats.get('avg_steps', 0):.1f}")
    typer.echo(f"Efficiency Score: {stats.get('efficiency_score', 0):.1f}")

    # Per-quest stats section
    quest_stats = details.get('quest_stats', [])
    if quest_stats:
        typer.echo("\n🎮 Quest Performance")
        typer.echo("-----------------")

        # Create a rich table for per-quest stats
        table = rich.table.Table()
        table.add_column("Quest", style="green")
        table.add_column("Runs", justify="right")
        table.add_column("Success Rate", justify="right")
        table.add_column("Avg Reward", justify="right")
        table.add_column("Avg Steps", justify="right")

        for quest in quest_stats:
            table.add_row(
                quest['quest'],
                str(quest['runs']),
                f"{quest['success_rate'] * 100:.1f}%",
                f"{quest['avg_reward']:.1f}",
                f"{quest['avg_steps']:.1f}",
            )

        console.print(table)

    # Recent runs section
    recent_runs = details.get('recent_runs', [])
    if recent_runs:
        typer.echo("\n🔄 Recent Runs")
        typer.echo("-----------")

        # Create a rich table for recent runs
        table = rich.table.Table()
        table.add_column("Quest", style="green")
        table.add_column("Date", style="blue")
        table.add_column("Outcome", style="cyan")
        table.add_column("Reward", justify="right")
        table.add_column("Steps", justify="right")

        for run in recent_runs:
            # Format start time
            start_time = run.get('start_time', '')
            if start_time and len(start_time) > 16:
                start_time = start_time[:16]  # Truncate to yyyy-mm-dd hh:mm

            # Set outcome style
            outcome = run.get('outcome', 'UNKNOWN')
            outcome_style = "green" if outcome == "SUCCESS" else "red"

            table.add_row(
                run.get('quest_name', 'unknown'),
                start_time,
                f"[{outcome_style}]{outcome}[/{outcome_style}]",
                f"{run.get('reward', 0) or 0:.1f}",
                str(run.get('step_count', len(run.get('steps', [])))),
            )

        console.print(table)
