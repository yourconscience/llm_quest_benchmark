"""Terminal renderer for Space Rangers quests using rich"""
from typing import Any, Dict

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from llm_quest_benchmark.utils import choice_mapper, text_processor


class TerminalRenderer:

    def __init__(self):
        self.console = Console()

    def render_title(self):
        """Render the game title with RPG-style ASCII art"""
        title = Text("\n✨ 🚀 Space Rangers Quest Player 🪐 ✨\n", style="bold magenta")
        subtitle = Text("Interactive Text Adventure Terminal Interface", style="cyan")
        self.console.print(
            Panel.fit(
                title.append(subtitle),
                border_style="bright_magenta",
                padding=(1, 4),
                subtitle="[bold yellow]v1.0[/]",
            )
        )

    def render_quest_text(self, text: str):
        """Render quest text with scroll effect"""
        cleaned_text = text_processor.clean_qm_text(text)
        panel = Panel.fit(
            f"[italic]{cleaned_text}[/]",
            title="[bold cyan]📜 Quest Log[/]",
            title_align="left",
            border_style="cyan",
            padding=(1, 4),
        )
        self.console.print(panel)

    def render_parameters(self, params: list):
        """Render quest parameters if any exist"""
        if not params:
            return

        param_table = Table.grid(padding=(0, 2))
        param_table.add_column(style="cyan", justify="right")
        param_table.add_column(style="green")

        for param in params:
            if isinstance(param, dict):
                # If the parameter is a dict, expect 'name' and 'value'
                param_name = param.get('name', '')
                param_value = param.get('value', '')
            else:
                # If it's not a dict, assume it's a string—clean it first.
                param_name = ""
                param_value = text_processor.clean_qm_text(str(param))
            param_table.add_row(param_name, param_value)

        self.console.print(
            Panel(
                param_table,
                title="Parameters",
                border_style="magenta",
                padding=(1, 2),
            ))
        self.console.print()

    def render_choices(self, choices: list):
        """Render choices with sequential numbers"""
        self.choice_mapper = choice_mapper.ChoiceMapper(choices)
        grid = Table.grid(padding=(0, 2), expand=False)
        grid.add_column(justify="right", width=6)
        grid.add_column(style="bold green", min_width=40)

        for i, choice in enumerate(choices, 1):
            grid.add_row(
                f"[reverse] {i} [/]",
                f"➤ {choice['text']}",
                end_section=True
            )

        self.console.print(
            Panel(
                grid,
                title="[bold green]🛡️  Available Actions[/]",
                subtitle="[dim](enter choice number)[/]",
                border_style="green",
                padding=(1, 2),
            )
        )

    def render_error(self, message: str):
        """Render error message"""
        self.console.print()
        self.console.print(Panel(
            f"[red]{message}[/]",
            border_style="red",
            title="[red]Error[/]",
        ))
        self.console.print()

    def render_game_state(self, state: Dict[str, Any]):
        """Render complete game state with RPG elements"""
        self.console.clear()  # Clear screen before rendering new state
        self.console.print("\n")
        self.render_quest_text(state['text'])

        if state.get('paramsState'):
            self.render_parameters(state['paramsState'])

        self.render_choices(state['choices'])
        self.console.print("\n")

    def prompt_choice(self, choice_mapper: choice_mapper.ChoiceMapper, skip: bool = False) -> int:
        # If skip is set and there is only one available choice, auto-select it.
        if skip and len(choice_mapper.get_valid_choices()) == 1:
            self.console.print("[dim]Auto-selecting the only available choice.[/dim]")
            return choice_mapper.get_jump_id(choice_mapper.get_valid_choices()[0])

        while True:
            try:
                choice = self.console.input("[bold yellow]Enter choice number (or 'q' to quit): [/]")
                if choice.lower() == 'q':
                    raise KeyboardInterrupt
                if not choice.isdigit():
                    self.render_error("Please enter a valid number")
                    continue
                choice_num = int(choice)
                if choice_num not in choice_mapper:
                    self.render_error(f"Invalid choice. Valid choices: {choice_mapper.get_valid_choices()}")
                    continue
                return choice_mapper.get_jump_id(choice_num)
            except KeyboardInterrupt:
                self.console.print("\n")
                raise