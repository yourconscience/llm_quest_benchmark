"""
Rich-based renderer for Space Rangers quests
"""
from typing import Dict, List, Optional, Any, Union

from rich.box import ROUNDED as RichRounded
from rich.console import Console as RichConsole
from rich.layout import Layout as RichLayout
from rich.panel import Panel as RichPanel
from rich.table import Table as RichTable
from rich.text import Text as RichText

from llm_quest_benchmark.environments.state import QMState


class QuestRenderer:
    """Rich-based renderer for Space Rangers quests"""

    def __init__(self, env):
        """Initialize renderer with environment"""
        self.env = env
        self.console = RichConsole()
        self.history: List[Dict[str, Any]] = []
        self.layout = self._create_layout()

    def _create_layout(self) -> RichLayout:
        """Create the base layout"""
        layout = RichLayout()

        layout.split(RichLayout(name="header", size=3), RichLayout(name="main"),
                     RichLayout(name="footer", size=3))

        layout["main"].split_row(
            RichLayout(name="content", ratio=2),
            RichLayout(name="sidebar", ratio=1),
        )

        return layout

    def _render_location(self, observation: str) -> RichPanel:
        """Render the current location"""
        return RichPanel(RichText(observation),
                         title="Current Location",
                         border_style="blue",
                         box=RichRounded)

    def _render_history(self) -> RichPanel:
        """Render action history"""
        table = RichTable(show_header=True, box=RichRounded)
        table.add_column("Step")
        table.add_column("Action")

        for i, entry in enumerate(self.history[-10:], 1):  # Show last 10 actions
            table.add_row(str(i), str(entry.get('action', '')))

        return RichPanel(table, title="History", border_style="green")

    def _render_analysis(self, analysis: Optional[str]) -> RichPanel:
        """Render agent's analysis if available"""
        if not analysis:
            return RichPanel("No analysis available", title="Analysis")

        return RichPanel(RichText(analysis),
                         title="Analysis",
                         border_style="yellow",
                         box=RichRounded)

    def _render_parameters(self, state: Union[Dict[str, Any], QMState]) -> RichTable:
        """Extract parameters from state"""
        params_table = RichTable(title="Quest Parameters")
        params_table.add_column("Parameter")
        params_table.add_column("Value")

        # Handle both dict and QMState objects
        if isinstance(state, dict):
            info = state.get('info', {})
        else:
            info = state.info if hasattr(state, 'info') else {}

        for param, value in info.items():
            params_table.add_row(str(param), str(value))
        return params_table

    def add_to_history(self, state: Union[Dict[str, Any], QMState]) -> None:
        """Add state to history"""
        # Convert QMState to dict for history tracking
        if isinstance(state, QMState):
            self.history.append({
                'action': '',  # Will be updated by step
                'text': state.text,
                'choices': state.choices,
                'reward': state.reward,
                'done': state.done,
                'info': state.info
            })
        else:
            self.history.append(state)

    def render(self) -> None:
        """Render current state"""
        # Get current state
        state = self.env.state
        observation = self.env.current_observation()

        # Update panels
        state_panel = self._render_location(observation)
        params_panel = self._render_parameters(state)
        history_panel = self._render_history()
        analysis_panel = self._render_analysis(
            self.history[-1].get('analysis') if self.history else None)

        # Update layout sections
        self.layout["main"]["content"].update(state_panel)
        self.layout["main"]["sidebar"].update(params_panel)
        self.layout["footer"].update(history_panel)

        # Preserve existing console handling
        self.console.clear()
        self.console.print(self.layout)
