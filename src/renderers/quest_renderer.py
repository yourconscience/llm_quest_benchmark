"""
Rich-based renderer for Space Rangers quests
"""
from typing import Dict, List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from rich.table import Table
from rich.text import Text
from rich.box import ROUNDED
import textarena as ta

class QuestRenderer(ta.Wrapper):
    """
    Rich-based renderer for quest state and history
    Wraps a TextArena environment to provide pretty terminal output
    """
    
    def __init__(self, env: ta.Env, show_analysis: bool = True):
        super().__init__(env)
        self.console = Console()
        self.show_analysis = show_analysis
        self.history: List[Dict] = []
        
    def _create_layout(self) -> Layout:
        """Create the base layout"""
        layout = Layout()
        
        layout.split(
            Layout(name="header", size=3),
            Layout(name="main"),
            Layout(name="footer", size=3)
        )
        
        layout["main"].split_row(
            Layout(name="content", ratio=2),
            Layout(name="sidebar", ratio=1),
        )
        
        return layout
        
    def _render_location(self, observation: str) -> Panel:
        """Render the current location"""
        return Panel(
            Text(observation),
            title="Current Location",
            border_style="blue",
            box=ROUNDED
        )
        
    def _render_history(self) -> Panel:
        """Render action history"""
        table = Table(show_header=True, box=ROUNDED)
        table.add_column("Step")
        table.add_column("Action")
        
        for i, entry in enumerate(self.history[-10:], 1):  # Show last 10 actions
            table.add_row(
                str(i),
                str(entry.get('action', ''))
            )
            
        return Panel(
            table,
            title="History",
            border_style="green"
        )
        
    def _render_analysis(self, analysis: Optional[str]) -> Panel:
        """Render agent's analysis if available"""
        if not analysis:
            return Panel("No analysis available", title="Analysis")
            
        return Panel(
            Text(analysis),
            title="Analysis",
            border_style="yellow",
            box=ROUNDED
        )
    
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
        """Render the current game state"""
        layout = self._create_layout()
        
        # Get current observation
        _, obs = self.env.get_observation()
        
        # Fill layout sections
        layout["header"].update(
            Panel("Space Rangers Quest", style="bold blue")
        )
        
        layout["content"].update(self._render_location(obs))
        
        sidebar_content = Layout()
        sidebar_content.split(
            Layout(self._render_history()),
            Layout(self._render_analysis(
                self.history[-1].get('analysis') if self.history and self.show_analysis else None
            ))
        )
        layout["sidebar"].update(sidebar_content)
        
        layout["footer"].update(
            Panel("Press Ctrl+C to exit", style="dim")
        )
        
        # Clear screen and render
        self.console.clear()
        self.console.print(layout) 