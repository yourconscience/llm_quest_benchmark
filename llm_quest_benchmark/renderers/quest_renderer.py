"""
Rich-based renderer for Space Rangers quests
"""
from typing import Dict, List, Optional
from rich.console import Console as RichConsole
from rich.panel import Panel as RichPanel
from rich.layout import Layout as RichLayout
from rich.table import Table as RichTable
from rich.text import Text as RichText
from rich.box import ROUNDED as RichRounded
import textarena as ta
from textarena.wrappers import RenderWrapper  # Add TextArena integration

class QuestRenderer(RenderWrapper):  # Change base class
    """
    Rich-based renderer for Space Rangers quests with TextArena integration
    Preserves existing history tracking while adding TextArena compatibility
    """

    def __init__(self, env: ta.Env, show_analysis: bool = True):
        super().__init__(env)  # Use RenderWrapper's init
        self.console = RichConsole()
        self.show_analysis = show_analysis
        self.history: List[Dict] = []
        self.layout = RichLayout()
        self._setup_layout()

    def _create_layout(self) -> RichLayout:
        """Create the base layout"""
        layout = RichLayout()

        layout.split(
            RichLayout(name="header", size=3),
            RichLayout(name="main"),
            RichLayout(name="footer", size=3)
        )

        layout["main"].split_row(
            RichLayout(name="content", ratio=2),
            RichLayout(name="sidebar", ratio=1),
        )

        return layout

    def _render_location(self, observation: str) -> RichPanel:
        """Render the current location"""
        return RichPanel(
            RichText(observation),
            title="Current Location",
            border_style="blue",
            box=RichRounded
        )

    def _render_history(self) -> RichPanel:
        """Render action history"""
        table = RichTable(show_header=True, box=RichRounded)
        table.add_column("Step")
        table.add_column("Action")

        for i, entry in enumerate(self.history[-10:], 1):  # Show last 10 actions
            table.add_row(
                str(i),
                str(entry.get('action', ''))
            )

        return RichPanel(
            table,
            title="History",
            border_style="green"
        )

    def _render_analysis(self, analysis: Optional[str]) -> RichPanel:
        """Render agent's analysis if available"""
        if not analysis:
            return RichPanel("No analysis available", title="Analysis")

        return RichPanel(
            RichText(analysis),
            title="Analysis",
            border_style="yellow",
            box=RichRounded
        )

    def _render_parameters(self, state) -> RichTable:
        """Extract parameters from TextArena state"""
        params_table = RichTable(title="Quest Parameters")
        params_table.add_column("Parameter")
        params_table.add_column("Value")
        for param, value in state.get('parameters', {}).items():
            params_table.add_row(str(param), str(value))
        return params_table

    def step(self, action):
        """Track action in history and render"""
        obs, reward, done, info = self.env.step(action)

        # Track history
        self.history.append({
            'action': action,
            'observation': obs,
            'reward': reward,
            'analysis': info.get('analysis')
        })

        # Render updated state
        self.render()

        return obs, reward, done, info

    def render(self, mode: str = "human") -> None:
        """Updated render method with TextArena compatibility"""
        # Get state through TextArena's interface
        state = self.env.state
        observation = self.env.current_observation()

        # Update panels using existing rendering logic
        state_panel = self._render_location(observation)
        params_panel = self._render_parameters(state)
        history_panel = self._render_history()
        analysis_panel = self._render_analysis(
            self.history[-1].get('analysis') if self.history and self.show_analysis else None
        )

        # Update layout sections
        self.layout["main"]["state"].update(state_panel)
        self.layout["main"]["params"].update(params_panel)
        self.layout["history"].update(history_panel)
        self.layout["sidebar"].update(analysis_panel)

        # Preserve existing console handling
        self.console.clear()
        self.console.print(self.layout)