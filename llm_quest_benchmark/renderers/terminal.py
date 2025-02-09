"""Terminal renderer for Space Rangers quests using rich"""
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from typing import Dict, Any

class TerminalRenderer:
    def __init__(self):
        self.console = Console()

    def render_title(self):
        """Render the game title"""
        self.console.print(Panel(
            "[bold blue]Space Rangers Quest Player[/bold blue]\n"
            "[dim]Interactive text quest player for Space Rangers[/dim]",
            border_style="blue"
        ))
        self.console.print()

    def render_quest_text(self, text: str):
        """Render the main quest text"""
        # Split paragraphs and format them
        paragraphs = text.split('\n\n')
        formatted_text = Text()

        for i, para in enumerate(paragraphs):
            if i > 0:
                formatted_text.append('\n\n')
            formatted_text.append(para.strip())

        self.console.print(Panel(
            formatted_text,
            title="Quest",
            border_style="blue",
            padding=(1, 1)
        ))

    def render_parameters(self, params: list):
        """Render quest parameters if any exist"""
        if not params:
            return

        param_table = Table.grid(padding=(0, 2))
        param_table.add_column(style="cyan", justify="right")
        param_table.add_column(style="green")

        for param in params:
            param_table.add_row(
                f"{param['name']}:",
                str(param['value'])
            )

        self.console.print(Panel(
            param_table,
            title="Parameters",
            border_style="magenta",
            padding=(0, 1)
        ))
        self.console.print()

    def render_choices(self, choices: list):
        """Render available choices"""
        if not choices:
            return

        # Create a compact choice list
        choice_grid = Table.grid(padding=(0, 1))
        choice_grid.add_column(style="yellow", justify="right", width=3)
        choice_grid.add_column(style="white")

        for i, choice in enumerate(choices, 1):
            if choice.get('active', True):
                choice_grid.add_row(
                    f"{i}.",
                    choice['text'].replace('\n', ' ')  # Make choices single-line
                )

        self.console.print(Panel(
            choice_grid,
            title="Actions",
            border_style="green",
            padding=(0, 1)
        ))

    def render_error(self, message: str):
        """Render error message"""
        self.console.print(f"[red]Error:[/red] {message}")

    def render_game_state(self, state: Dict[str, Any]):
        """Render complete game state"""
        self.render_quest_text(state['text'])
        self.render_parameters(state['paramsState'])
        self.render_choices(state['choices'])