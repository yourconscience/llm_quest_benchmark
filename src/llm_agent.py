"""
LLM-powered decision maker for text quests
"""
import os
import litellm
from jinja2 import Environment, FileSystemLoader
from typing import List
from .data_structures import QuestState, QMTransition

class QuestAgent:
    def __init__(self, model: str = "openrouter/deepseek/deepseek-chat", template_dir: str = "prompts"):
        self.model = model
        self.template_env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=True
        )
        self.fallback_model = "openrouter/anthropic/claude-3.5-sonnet"
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable not set")

    def choose_action(
        self,
        state: QuestState,
        transitions: List[QMTransition]
    ) -> int:
        """Select transition index using LLM with enhanced validation"""
        if not transitions:
            raise ValueError("No available transitions")

        prompt = self.render_prompt(state, transitions)
        response = self.query_llm(prompt)
        return self.validate_response(response, len(transitions))

    def render_prompt(self, state: QuestState, transitions: List[QMTransition]) -> str:
        template = self.template_env.get_template("decision_prompt.jinja2")
        return template.render(
            location=state.current_location,
            params=state.parameters,
            transitions=transitions,
            history=state.history[-3:]  # Last 3 steps
        )

    def query_llm(self, prompt: str) -> str:
        """LiteLLM integration with OpenRouter fallback"""
        try:
            response = litellm.completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
                api_key=self.api_key
            )
            return response.choices[0].message.content
        except Exception as e:
            # Fallback to Claude-3.5-Sonnet
            return litellm.completion(
                model=self.fallback_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                api_key=self.api_key
            ).choices[0].message.content

    def validate_response(self, text: str, num_choices: int) -> int:
        """Validate and parse LLM response"""
        clean_text = text.strip().lower()

        # Look for explicit choice numbers
        for i in range(1, num_choices + 1):
            if any(pattern.format(i) in clean_text
                   for pattern in ["{}", "option {}", "choice {}"]):
                return i - 1

        # Fallback to first option
        return 0