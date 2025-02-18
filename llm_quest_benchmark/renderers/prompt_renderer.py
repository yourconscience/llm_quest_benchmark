"""
Prompt renderer and history tracker for Space Rangers quests
"""
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, Template

from llm_quest_benchmark.dataclasses.state import QMState
from llm_quest_benchmark.constants import PROMPT_TEMPLATES_DIR, DEFAULT_TEMPLATE


class PromptRenderer:
    """Handles prompt rendering and history tracking for quests"""

    def __init__(self, env, templates_dir: Optional[Path] = None, template: str = DEFAULT_TEMPLATE):
        """Initialize renderer with environment and templates"""
        self.env = env
        self.history: List[Dict[str, Any]] = []
        self.template = template

        # Initialize Jinja environment
        self.templates_dir = templates_dir or PROMPT_TEMPLATES_DIR
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            trim_blocks=True,
            lstrip_blocks=True
        )
        self._load_templates()

    def _load_templates(self) -> None:
        """Load all template files"""
        self.action_template = self.jinja_env.get_template(self.template)
        self.system_template = self.jinja_env.get_template("system_role.jinja")

    def render_action_prompt(self, observation: str, choices: list) -> str:
        """Render the action choice prompt"""
        return self.action_template.render(
            observation=observation,
            choices=[{"text": c["text"]} for c in choices]
        )

    def render_system_prompt(self, **kwargs) -> str:
        """Render the system role prompt"""
        return self.system_template.render(**kwargs)

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

    def get_template(self, template_name: str) -> Template:
        """Get a specific template by name"""
        return self.jinja_env.get_template(template_name)

    def get_history(self, last_n: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get history, optionally limited to last N entries"""
        if last_n is not None:
            return self.history[-last_n:]
        return self.history
