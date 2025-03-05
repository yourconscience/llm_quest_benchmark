"""Prompt renderer and history tracker for LLM agents"""
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, Template

from llm_quest_benchmark.constants import (
    ACTION_TEMPLATES_DIR,
    DEFAULT_TEMPLATE,
    PROMPT_TEMPLATES_DIR,
    SYSTEM_ROLE_TEMPLATE,
    SYSTEM_TEMPLATES_DIR,
)
from llm_quest_benchmark.schemas.state import QMState

logger = logging.getLogger(__name__)


class PromptRenderer:
    """Handles prompt rendering and history tracking for LLM agents"""

    def __init__(self,
                 env,
                 templates_dir: Optional[Path] = None,
                 system_template: str = SYSTEM_ROLE_TEMPLATE,
                 action_template: str = DEFAULT_TEMPLATE,
                 memory_config: Optional[Dict[str, Any]] = None):
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
        self.memory_config = memory_config or {"type": "message_history", "max_history": 10}

        # Handle template paths with or without directory prefixes
        self.system_template_name = self._normalize_template_path(system_template, "system")
        self.action_template_name = self._normalize_template_path(action_template, "action")

        # Create a loader that checks both the main templates directory and the subdirectories
        self.jinja_env = Environment(loader=ChoiceLoader([
            FileSystemLoader(self.templates_dir),
            FileSystemLoader(SYSTEM_TEMPLATES_DIR.parent),
            FileSystemLoader(ACTION_TEMPLATES_DIR.parent)
        ]),
                                     trim_blocks=True,
                                     lstrip_blocks=True)

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

        # Empty history case
        if not recent_history:
            return {"memory": []}

        # For "message_history" type, just return the raw history
        if memory_type == "message_history":
            return {"memory": recent_history}
        # For "summary" type, generate a summary of the history using LLM
        elif memory_type == "summary":
            try:
                summary = self._generate_history_summary(recent_history)
                return {"memory": summary}
            except Exception as e:
                logger.error(f"Error generating history summary: {e}")
                # Fallback to simple summary if LLM summarization fails
                return self._generate_simple_summary(recent_history)
        else:
            logger.warning(f"Unknown memory type: {memory_type}")
            return {"memory": []}

    def _generate_simple_summary(self, history: List[Dict[str, Any]]) -> str:
        """Generate a simple summary of history without using LLM

        Args:
            history (List[Dict[str, Any]]): History entries

        Returns:
            str: Simple summary of history
        """
        summary = []
        for i, entry in enumerate(history):
            state_summary = f"State {i+1}: {entry.get('text', '')[:100]}..."
            action_summary = f"Action {i+1}: {entry.get('action', '')}"
            summary.append(f"{state_summary}\n{action_summary}")

        return "\n\n".join(summary)

    def _generate_history_summary(self, history: List[Dict[str, Any]]) -> str:
        """Generate a summary of history using LLM

        Args:
            history (List[Dict[str, Any]]): History entries

        Returns:
            str: LLM-generated summary of history
        """
        # Import here to avoid circular imports
        from llm_quest_benchmark.llm.client import get_llm_client

        # Format history for summarization
        history_text = []
        for i, entry in enumerate(history):
            state_text = entry.get('text', '')
            action = entry.get('action', 'No action')
            history_text.append(f"STATE {i+1}:\n{state_text}\n\nACTION {i+1}:\n{action}")

        history_prompt = "\n\n".join(history_text)

        # Create prompt for summarization
        prompt = f"""Below is a history of states and actions from an interactive text adventure.
Please provide a concise summary (200-300 words) that captures:
1. Key plot developments
2. Important decisions made by the player
3. Current situation and objectives

HISTORY:
{history_prompt}

SUMMARY:"""

        # Use Claude-3.5-Sonnet or GPT-4o for summarization
        try:
            # Try Claude first
            llm = get_llm_client("claude-3-5-sonnet-latest", temperature=0.2)
            summary = llm.get_completion(prompt)
        except Exception as e:
            logger.warning(f"Failed to use Claude for summarization: {e}, falling back to GPT-4o")
            try:
                # Fall back to GPT-4o
                llm = get_llm_client("gpt-4o", temperature=0.2)
                summary = llm.get_completion(prompt)
            except Exception as e2:
                logger.error(f"Failed to generate summary with GPT-4o: {e2}")
                raise

        return summary

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

        return self.action_template.render(observation=observation,
                                           choices=[{
                                               "text": c["text"]
                                           } for c in choices],
                                           **memory_context)

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
