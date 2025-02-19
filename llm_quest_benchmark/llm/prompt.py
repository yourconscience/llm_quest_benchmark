"""Prompt renderer and history tracker for LLM agents"""
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, Template

from llm_quest_benchmark.dataclasses.state import QMState
from llm_quest_benchmark.constants import PROMPT_TEMPLATES_DIR, DEFAULT_TEMPLATE


class PromptRenderer:
    """Handles prompt rendering and history tracking for LLM agents"""

    def __init__(self, env, templates_dir: Optional[Path] = None, template: str = DEFAULT_TEMPLATE):
        """Initialize renderer with environment and templates

        Args:
            env: Environment instance (can be None for standalone use)
            templates_dir (Optional[Path], optional): Directory containing templates. Defaults to None.
            template (str, optional): Template name to use. Defaults to DEFAULT_TEMPLATE.
        """
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
        """Render the action choice prompt

        Args:
            observation (str): Current game state observation
            choices (list): List of available choices

        Returns:
            str: Rendered prompt for action selection
        """
        return self.action_template.render(
            observation=observation,
            choices=[{"text": c["text"]} for c in choices]
        )

    def render_system_prompt(self, **kwargs) -> str:
        """Render the system role prompt

        Args:
            **kwargs: Additional template variables

        Returns:
            str: Rendered system prompt
        """
        return self.system_template.render(**kwargs)

    def add_to_history(self, state: Union[Dict[str, Any], QMState]) -> None:
        """Add state to history

        Args:
            state (Union[Dict[str, Any], QMState]): State to add to history
        """
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
        """Get a specific template by name

        Args:
            template_name (str): Name of the template to get

        Returns:
            Template: Jinja template instance
        """
        return self.jinja_env.get_template(template_name)

    def get_history(self, last_n: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get history, optionally limited to last N entries

        Args:
            last_n (Optional[int], optional): Number of entries to return. Defaults to None.

        Returns:
            List[Dict[str, Any]]: History entries
        """
        if last_n is not None:
            return self.history[-last_n:]
        return self.history