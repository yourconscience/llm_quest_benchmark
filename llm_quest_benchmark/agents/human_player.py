"""Human player interface for Space Rangers quests"""
import logging
from typing import Dict, Any, Optional

from rich.console import Console
from rich.panel import Panel

from llm_quest_benchmark.agents.base import QuestPlayer


class HumanPlayer(QuestPlayer):
    """Human player that takes input through console"""

    def __init__(self, skip_single: bool = False, debug: bool = False):
        """Initialize human player

        Args:
            skip_single: Auto-select when only one choice available
            debug: Enable debug logging
        """
        self.skip_single = skip_single
        self.debug = debug
        self.console = Console()
        self.logger = logging.getLogger(self.__class__.__name__)
        if debug:
            self.logger.setLevel(logging.DEBUG)

    def get_action(self, observation: str, choices: list) -> str:
        """Get action through console input"""
        # Auto-skip if enabled and only one choice
        if self.skip_single and len(choices) == 1:
            self.console.print("[dim]Auto-selecting the only available choice.[/dim]")
            return "1"

        # Get user input
        while True:
            try:
                choice = self.console.input("[bold yellow]Enter choice number (or 'q' to quit): [/]")
                if choice.lower() == 'q':
                    raise KeyboardInterrupt

                if not choice.isdigit():
                    self.console.print("[red]Please enter a valid number[/]")
                    continue

                choice_num = int(choice)
                if not (1 <= choice_num <= len(choices)):
                    self.console.print(f"[red]Invalid choice. Valid choices: 1-{len(choices)}[/]")
                    continue

                return str(choice_num)

            except KeyboardInterrupt:
                self.console.print("\n[yellow]Quest aborted by user[/]")
                raise

    def reset(self) -> None:
        """Nothing to reset for human player"""
        pass

    def on_game_start(self) -> None:
        """Show welcome message"""
        self.console.print(
            Panel.fit(
                "Welcome to Space Rangers Quest!\n"
                "Enter choice numbers to play, 'q' to quit.",
                title="[bold magenta]🚀 Quest Started[/]",
                border_style="magenta"
            )
        )

    def on_game_end(self, final_state: Dict[str, Any]) -> None:
        """Show game end message"""
        reward = final_state.get('reward', 0)
        style = "green" if reward > 0 else "red"
        message = "Quest completed successfully!" if reward > 0 else "Quest failed."

        self.console.print(
            Panel.fit(
                f"{message}\nFinal reward: {reward}",
                title=f"[bold {style}]🏁 Quest Ended[/]",
                border_style=style
            )
        )