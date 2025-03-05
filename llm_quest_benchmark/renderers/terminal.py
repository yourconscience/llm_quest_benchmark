"""Terminal renderer for Space Rangers quests using rich"""
from typing import Any, Dict, Optional

from rich.console import Console

from llm_quest_benchmark.constants import READABILITY_DELAY
from llm_quest_benchmark.renderers.base import BaseRenderer
from llm_quest_benchmark.schemas.response import LLMResponse
from llm_quest_benchmark.schemas.state import AgentState
from llm_quest_benchmark.utils import choice_mapper, text_processor


class NoRenderer:

    def render_game_state(self, state: AgentState):
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

    def render_game_state(self, state: AgentState):
        """Render game state"""
        self.console.clear()
        self.step_number = state.step

        # Print step separator
        self.console.print(f"\n{'='*80}", style="blue")
        self.console.print(f"Step {self.step_number}", style="bold blue")
        self.console.print(f"{'='*80}\n", style="blue")

        # Show LLM response first
        self.render_llm_response(state.llm_response)
        # Add separator after LLM response
        self.console.print(f"\n{'-'*40}\n", style="dim")

        self.render_quest_text(state.observation)
        self.render_choices(state.choices)

    def render_llm_response(self, response: LLMResponse):
        """Render LLM's response"""
        self.console.print("\n[yellow bold]Agent's Thoughts:[/]")
        if response.analysis:
            self.console.print(f"[yellow]{response.analysis.strip()}[/]")
        if response.reasoning:
            self.console.print(f"[yellow]{response.reasoning.strip()}[/]")
        self._sleep_for_readability(READABILITY_DELAY)

    def prompt_choice(self, choice_mapper: choice_mapper.ChoiceMapper, skip: bool = False) -> int:
        if skip and len(choice_mapper.get_valid_choices()) == 1:
            self.console.print("[dim]Auto-selecting the only available choice.[/]")
            return choice_mapper.get_jump_id(choice_mapper.get_valid_choices()[0])

        while True:
            try:
                choice = self.console.input(
                    "\n[bold yellow]Enter choice number (or 'q' to quit): [/]")
                if choice.lower() == 'q':
                    raise KeyboardInterrupt
                if not choice.isdigit():
                    self.render_error("Please enter a valid number")
                    continue
                choice_num = int(choice)
                if choice_num not in choice_mapper:
                    self.render_error(
                        f"Invalid choice. Valid choices: {choice_mapper.get_valid_choices()}")
                    continue
                return choice_mapper.get_jump_id(choice_num)
            except KeyboardInterrupt:
                self.console.print("\n")
                raise
