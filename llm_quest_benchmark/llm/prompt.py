"""Prompt renderer and history tracker for LLM agents"""
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import os
import logging
import json
import re
from jinja2 import Environment, FileSystemLoader, Template, ChoiceLoader

from llm_quest_benchmark.schemas.state import QMState
from llm_quest_benchmark.constants import (
    PROMPT_TEMPLATES_DIR,
    SYSTEM_TEMPLATES_DIR,
    ACTION_TEMPLATES_DIR,
    DEFAULT_TEMPLATE,
    SYSTEM_ROLE_TEMPLATE
)

logger = logging.getLogger(__name__)


class PromptRenderer:
    """Handles prompt rendering and history tracking for LLM agents"""

    def __init__(
        self,
        env,
        templates_dir: Optional[Path] = None,
        system_template: str = SYSTEM_ROLE_TEMPLATE,
        action_template: str = DEFAULT_TEMPLATE,
        memory_config: Optional[Dict[str, Any]] = None
    ):
        """Initialize renderer with environment and templates

        Args:
            env: Environment instance (can be None for standalone use)
            templates_dir (Optional[Path], optional): Directory containing templates. Defaults to None.
            system_template (str, optional): System template name to use. Defaults to SYSTEM_ROLE_TEMPLATE.
            action_template (str, optional): Action template name to use. Defaults to DEFAULT_TEMPLATE.
            memory_config (Optional[Dict[str, Any]], optional): Memory configuration. Defaults to None.
        """
        self.env = env
        self.history: List[Dict[str, Any]] = []
        self.templates_dir = templates_dir or PROMPT_TEMPLATES_DIR
        
        # Set memory configuration
        self.memory_config = memory_config or {
            "type": "message_history",
            "max_history": 10
        }
        
        # Handle template paths with or without directory prefixes
        self.system_template_name = self._normalize_template_path(system_template, "system")
        self.action_template_name = self._normalize_template_path(action_template, "action")
        
        # Create a loader that checks both the main templates directory and the subdirectories
        self.jinja_env = Environment(
            loader=ChoiceLoader([
                FileSystemLoader(self.templates_dir),
                FileSystemLoader(SYSTEM_TEMPLATES_DIR.parent),
                FileSystemLoader(ACTION_TEMPLATES_DIR.parent)
            ]),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        self._load_templates()
        self._load_template_contents()

    def _normalize_template_path(self, template_path: str, default_type: str) -> str:
        """Normalize template path to include directory prefix if missing

        Args:
            template_path (str): Template path or name
            default_type (str): Default type (system or action) if no directory specified

        Returns:
            str: Normalized template path
        """
        # If template already includes directory part, return as is
        if "/" in template_path or "\\" in template_path:
            return template_path
        
        # Otherwise, add proper directory prefix
        if default_type == "system":
            return f"system/{template_path}"
        else:
            return f"action/{template_path}"

    def _load_templates(self) -> None:
        """Load Jinja template objects"""
        try:
            self.action_template = self.jinja_env.get_template(self.action_template_name)
            self.system_template = self.jinja_env.get_template(self.system_template_name)
        except Exception as e:
            logger.error(f"Error loading templates: {e}")
            # Fall back to default templates if specified ones can't be loaded
            self.action_template_name = DEFAULT_TEMPLATE
            self.system_template_name = SYSTEM_ROLE_TEMPLATE
            self.action_template = self.jinja_env.get_template(self.action_template_name)
            self.system_template = self.jinja_env.get_template(self.system_template_name)

    def _load_template_contents(self):
        """Load raw template contents for UI"""
        try:
            # Try to find template under templates directory first
            full_action_path = self.templates_dir / self.action_template_name
            if not full_action_path.exists():
                # If not found, try with action templates directory
                action_name = os.path.basename(self.action_template_name)
                full_action_path = ACTION_TEMPLATES_DIR / action_name
            
            full_system_path = self.templates_dir / self.system_template_name
            if not full_system_path.exists():
                # If not found, try with system templates directory
                system_name = os.path.basename(self.system_template_name)
                full_system_path = SYSTEM_TEMPLATES_DIR / system_name
            
            self.action_template_content = full_action_path.read_text(encoding="utf-8")
            self.system_template_content = full_system_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Error loading template contents: {e}")
            self.action_template_content = "Error loading template content"
            self.system_template_content = "Error loading template content"

    def _get_memory_context(self) -> Dict[str, Any]:
        """Get memory context for templates based on memory configuration

        Returns:
            Dict[str, Any]: Memory context for templates
        """
        memory_type = self.memory_config.get("type", "message_history")
        max_history = self.memory_config.get("max_history", 10)
        
        # Get most recent history based on max_history
        recent_history = self.get_history(max_history)
        
        # For "message_history" type, just return the raw history
        if memory_type == "message_history":
            return {
                "memory": recent_history
            }
        # For "summary" type, generate a summary of the history
        elif memory_type == "summary":
            # TODO: Implement real summarization using LLM
            # For now, just create a simple summary of states and actions
            summary = []
            for i, entry in enumerate(recent_history):
                state_summary = f"State {i+1}: {entry.get('text', '')[:100]}..."
                action_summary = f"Action {i+1}: {entry.get('action', '')}"
                summary.append(f"{state_summary}\n{action_summary}")
            
            return {
                "memory": "\n\n".join(summary)
            }
        else:
            logger.warning(f"Unknown memory type: {memory_type}")
            return {
                "memory": []
            }

    def render_action_prompt(self, observation: str, choices: list) -> str:
        """Render the action choice prompt

        Args:
            observation (str): Current game state observation
            choices (list): List of available choices

        Returns:
            str: Rendered prompt for action selection
        """
        # Get memory context
        memory_context = self._get_memory_context()
        
        return self.action_template.render(
            observation=observation,
            choices=[{"text": c["text"]} for c in choices],
            **memory_context
        )

    def render_system_prompt(self, **kwargs) -> str:
        """Render the system role prompt

        Args:
            **kwargs: Additional template variables

        Returns:
            str: Rendered system prompt
        """
        # Get memory context
        memory_context = self._get_memory_context()
        
        # Merge kwargs with memory context
        context = {**kwargs, **memory_context}
        
        return self.system_template.render(**context)

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

    def get_system_template_content(self) -> str:
        """Get raw system template content"""
        return self.system_template_content

    def get_action_template_content(self) -> str:
        """Get raw action template content"""
        return self.action_template_content
        
    def set_memory_config(self, memory_config: Dict[str, Any]) -> None:
        """Set memory configuration

        Args:
            memory_config (Dict[str, Any]): Memory configuration
        """
        self.memory_config = memory_config

    def handle_calculator_tool(self, request: str) -> str:
        """Handle calculator tool request

        Args:
            request (str): Calculator request string

        Returns:
            str: Calculator response
        """
        # Simple calculator implementation
        try:
            # Remove common text patterns like "calculate" or "what is"
            clean_request = request.lower()
            clean_request = re.sub(r'calculate\s+', '', clean_request)
            clean_request = re.sub(r'what\s+is\s+', '', clean_request)
            clean_request = re.sub(r'compute\s+', '', clean_request)
            
            # Evaluate the expression
            result = eval(clean_request)
            return f"Calculator result: {result}"
        except Exception as e:
            logger.error(f"Calculator error: {e}")
            return f"Calculator error: {str(e)}"