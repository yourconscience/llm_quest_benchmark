"""LLM agent for Space Rangers quests"""
import json
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from llm_quest_benchmark.constants import MODEL_CHOICES, DEFAULT_TEMPLATE
from llm_quest_benchmark.agents.llm_client import get_llm_client
from llm_quest_benchmark.agents.base import QuestPlayer
from llm_quest_benchmark.renderers.prompt_renderer import PromptRenderer


@dataclass
class LLMResponse:
    """Structured response from LLM agent"""
    action: int  # The chosen action number (1-based)
    reasoning: Optional[str] = None  # Optional explanation for the choice

    def to_choice_string(self) -> str:
        """Convert to choice string (1-based action number)"""
        return str(self.action)


def parse_llm_response(response: str, num_choices: int, debug: bool = False, logger: Optional[logging.Logger] = None) -> LLMResponse:
    """Parse LLM response and return structured response object."""
    if debug and logger:
        logger.debug(f"Raw LLM response: {response}")

    default_response = LLMResponse(action=1)  # Default to first choice if parsing fails

    try:
        # Try to parse as JSON first
        try:
            from json_repair import repair_json
            try:
                response_json = json.loads(response)
            except json.JSONDecodeError:
                # Try to repair and parse JSON
                repaired_json = repair_json(response)
                response_json = json.loads(repaired_json)

            if isinstance(response_json, dict) and 'action' in response_json:
                try:
                    action = int(response_json['action'])
                    if 1 <= action <= num_choices:
                        return LLMResponse(
                            action=action,
                            reasoning=response_json.get('reasoning')
                        )
                    else:
                        if debug and logger:
                            logger.error(f"Action number {action} out of range [1, {num_choices}]")
                except (ValueError, TypeError):
                    if debug and logger:
                        logger.error(f"Invalid action value in JSON: {response_json['action']}")
            else:
                # Try parsing as plain number
                try:
                    action = int(response.strip())
                    if 1 <= action <= num_choices:
                        return LLMResponse(action=action)
                    else:
                        if debug and logger:
                            logger.error(f"Action number {action} out of range [1, {num_choices}]")
                except ValueError:
                    if debug and logger:
                        logger.error(f"Could not parse response as number: {response}")

        except (ImportError, json.JSONDecodeError) as e:
            if debug and logger:
                logger.error(f"JSON parsing failed: {str(e)}")
            # Try parsing as plain number
            try:
                action = int(response.strip())
                if 1 <= action <= num_choices:
                    return LLMResponse(action=action)
                else:
                    if debug and logger:
                        logger.error(f"Action number {action} out of range [1, {num_choices}]")
            except ValueError:
                if debug and logger:
                    logger.error(f"Could not parse response as number: {response}")

    except Exception as e:
        if debug and logger:
            logger.error(f"Response parsing failed: {str(e)}")

    return default_response


class LLMAgent(QuestPlayer):
    """LLM-powered agent for Space Rangers quests"""

    SUPPORTED_MODELS = MODEL_CHOICES

    def __init__(self, debug: bool = False, model_name: str = "gpt-4o", template: str = DEFAULT_TEMPLATE, skip_single: bool = False):
        super().__init__(skip_single=skip_single)
        self.debug = debug
        self.model_name = model_name.lower()
        self.template = template

        if self.model_name not in self.SUPPORTED_MODELS:
            raise ValueError(f"Unsupported model: {model_name}. Supported models are: {self.SUPPORTED_MODELS}")

        self.logger = logging.getLogger(self.__class__.__name__)
        if self.debug:
            self.logger.setLevel(logging.DEBUG)
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(name)s - %(message)s'))
            self.logger.addHandler(handler)

        # Initialize prompt renderer
        self.prompt_renderer = PromptRenderer(None, template=template)  # None for env since we don't need it here

        # Initialize LLM client with system prompt
        self.llm = get_llm_client(model_name, system_prompt=self.prompt_renderer.render_system_prompt())
        self.history: List[LLMResponse] = []

    def _get_action_impl(self, observation: str, choices: list) -> str:
        """Implementation of action selection logic"""
        if self.debug:
            self.logger.debug(f"\nObservation:\n{observation}")

        # Render prompt using template
        prompt = self.prompt_renderer.render_action_prompt(observation, choices)
        if self.debug:
            self.logger.debug(f"\nPrompt:\n{prompt}")

        try:
            response = self.llm(prompt)
            llm_response = parse_llm_response(response, len(choices), self.debug, self.logger)

            if self.debug and llm_response.reasoning:
                self.logger.debug(f"Reasoning: {llm_response.reasoning}")

            # Store response in history
            self.history.append(llm_response)

            return llm_response.to_choice_string()

        except Exception as e:
            self.logger.error(f"LLM call failed: {str(e)}")
            return "1"  # Default to first choice

    def reset(self) -> None:
        """Reset agent state"""
        self.history = []

    def on_game_end(self, final_state: Dict[str, Any]) -> None:
        """Log final state for analysis"""
        if self.debug:
            self.logger.debug(f"Game ended with state: {final_state}")