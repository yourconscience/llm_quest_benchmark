"""Terminal renderer for Space Rangers quests using rich"""
from typing import Any, Dict
from rich.console import Console
from llm_quest_benchmark.renderers.base import BaseRenderer
from llm_quest_benchmark.utils import choice_mapper, text_processor
from llm_quest_benchmark.constants import READABILITY_DELAY

class NoRenderer:
    def render_game_state(self, state: Dict[str, Any]):
        """Render complete game state with RPG elements"""
        pass

    def render_title(self):
        """Render the game title with RPG-style ASCII art"""
        pass


class RichRenderer(BaseRenderer):
    """Rich Console renderer for Space Rangers quests"""

    def __init__(self):
        self.console = Console()
        self.step_number = 0

    def render_title(self):
        """Render the game title"""
        self.console.print("\n✨ Space Rangers Quest Player ✨\n", style="bold magenta")

    def render_quest_text(self, text: str):
        """Render quest text"""
        cleaned_text = text_processor.clean_qm_text(text)
        self.console.print("\n[cyan]" + cleaned_text + "[/]")
        self._sleep_for_readability(1.0)

    def render_parameters(self, params: list):
        """Render quest parameters if any exist"""
        if not params:
            return
        self.console.print("\nParameters:", style="bold")
        for param in params:
            if isinstance(param, dict):
                self.console.print(f"{param.get('name', '')}: {param.get('value', '')}")
            else:
                cleaned_param = text_processor.clean_qm_text(str(param))
                self.console.print(cleaned_param)

    def render_choices(self, choices: list):
        """Render choices with numbers"""
        self.choice_mapper = choice_mapper.ChoiceMapper(choices)
        self.console.print("\nChoices:", style="bold green")
        for i, choice in enumerate(choices, 1):
            cleaned_text = text_processor.clean_qm_text(choice['text'])
            self.console.print(f"{i}. {cleaned_text}", style="green")

    def render_error(self, message: str):
        """Render error message"""
        self.console.print(f"\nError: {message}", style="red bold")

    def render_game_state(self, state: Dict[str, Any]):
        """Render game state"""
        self.console.clear()
        self.step_number += 1

        # Print step separator
        self.console.print(f"\n{'='*80}", style="blue")
        self.console.print(f"Step {self.step_number}", style="bold blue")
        self.console.print(f"{'='*80}\n", style="blue")

        # If there's an LLM response, show it first
        if state.get('llm_response'):
            self.render_llm_response(state['llm_response'])
            # Add separator after LLM response
            self.console.print(f"\n{'-'*40}\n", style="dim")
        elif self.step_number != 1:
            self.render_quest_text(str(state))
            raise Exception(f"No LLM response. State: {state}")

        self.render_quest_text(state['text'])

        if state.get('paramsState'):
            self.render_parameters(state['paramsState'])

        self.render_choices(state['choices'])

    def render_llm_response(self, response: str):
        """Render LLM's response"""
        if not response:  # Skip if response is empty
            return

        self.console.print("\n[yellow bold]Agent's Thoughts:[/]")
        # Split into reasoning and choice if possible
        parts = response.split("Final Answer:", 1)
        if len(parts) > 1:
            reasoning, choice = parts
            self.console.print(f"[yellow]{reasoning.strip()}[/]")
            self.console.print("\n[green bold]Final Choice:[/]")
            self.console.print(f"[green]{choice.strip()}[/]")
        else:
            self.console.print(f"[yellow]{response.strip()}[/]")
        self._sleep_for_readability(READABILITY_DELAY)

    def prompt_choice(self, choice_mapper: choice_mapper.ChoiceMapper, skip: bool = False) -> int:
        if skip and len(choice_mapper.get_valid_choices()) == 1:
            self.console.print("[dim]Auto-selecting the only available choice.[/]")
            return choice_mapper.get_jump_id(choice_mapper.get_valid_choices()[0])

        while True:
            try:
                choice = self.console.input("\n[bold yellow]Enter choice number (or 'q' to quit): [/]")
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