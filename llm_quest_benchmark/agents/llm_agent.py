"""LLM agent for Space Rangers quests"""
import json
import logging
from typing import Dict, List, Any, Optional
from json_repair import repair_json

from llm_quest_benchmark.constants import (
    MODEL_CHOICES,
    DEFAULT_TEMPLATE,
    DEFAULT_TEMPERATURE,
    DEFAULT_MODEL
)
from llm_quest_benchmark.llm.client import get_llm_client
from llm_quest_benchmark.llm.prompt import PromptRenderer
from llm_quest_benchmark.agents.base import QuestPlayer
from llm_quest_benchmark.dataclasses.response import LLMResponse


def _parse_json_response(response: str, debug: bool = False, logger: Optional[logging.Logger] = None) -> Optional[Dict[str, Any]]:
    """Try to parse response as JSON, with repair attempt if needed"""
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        if debug and logger:
            logger.debug("Initial JSON parse failed, attempting repair")
        try:
            repaired = repair_json(response)
            return json.loads(repaired)
        except Exception as e:
            if debug and logger:
                logger.error(f"JSON repair failed: {e}")
            return None


def _validate_action_number(action: int, num_choices: int, debug: bool = False, logger: Optional[logging.Logger] = None) -> bool:
    """Validate that action number is within valid range"""
    if 1 <= action <= num_choices:
        return True
    if debug and logger:
        logger.error(f"Action number {action} out of range [1, {num_choices}]")
    return False


def parse_llm_response(response: str, num_choices: int, debug: bool = False, logger: Optional[logging.Logger] = None) -> LLMResponse:
    """Parse LLM response and return structured response object."""
    if debug and logger:
        logger.debug(f"Raw LLM response: {response}")

    # Try parsing as JSON first
    response_json = _parse_json_response(response, debug, logger)
    if response_json and isinstance(response_json, dict):
        # Check for either 'action' or 'result' field
        action_value = response_json.get('action') or response_json.get('result')
        if action_value is not None:
            try:
                action = int(action_value)
                if _validate_action_number(action, num_choices, debug, logger):
                    return LLMResponse(
                        action=action,
                        reasoning=response_json.get('reasoning'),
                        is_default=False
                    )
            except (ValueError, TypeError):
                if debug and logger:
                    logger.error(f"Invalid action value in JSON: {action_value}")

    # Try parsing as plain number
    try:
        action = int(response.strip())
        if _validate_action_number(action, num_choices, debug, logger):
            return LLMResponse(action=action, is_default=False)
    except ValueError:
        if debug and logger:
            logger.error(f"Could not parse response as number: {response}")

    # Default to first choice if all parsing attempts fail
    if debug and logger:
        logger.error(f"Error during response parsing, defaulting to first choice. Response: {response[:100]}...")
    return LLMResponse(action=1, is_default=True)


class LLMAgent(QuestPlayer):
    """LLM-powered agent for Space Rangers quests"""

    SUPPORTED_MODELS = MODEL_CHOICES

    def __init__(self,
                 debug: bool = False,
                 model_name: str = DEFAULT_MODEL,
                 template: str = DEFAULT_TEMPLATE,
                 skip_single: bool = False,
                 temperature: float = DEFAULT_TEMPERATURE):
        super().__init__(skip_single=skip_single)
        self.debug = debug
        self.model_name = model_name.lower()
        self.template = template
        self.temperature = temperature

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

        # Initialize LLM client with system prompt and temperature
        self.llm = get_llm_client(
            model_name,
            system_prompt=self.prompt_renderer.render_system_prompt(),
            temperature=temperature
        )
        self.history: List[LLMResponse] = []

    def get_last_response(self) -> LLMResponse:
        """Get the last LLM response from history"""
        return self.history[-1]

    def _get_action_impl(self, observation: str, choices: list) -> int:
        """Implementation of action selection logic"""
        if self.debug:
            self.logger.debug(f"\nObservation:\n{observation}")
            self.logger.debug(f"Available choices: {choices}")

        # Render prompt using template
        prompt = self.prompt_renderer.render_action_prompt(observation, choices)
        if self.debug:
            self.logger.debug(f"\nPrompt:\n{prompt}")

        try:
            response = self.llm(prompt)
            if self.debug:
                self.logger.debug(f"Raw LLM response: {response}")

            llm_response = parse_llm_response(response, len(choices), self.debug, self.logger)
            if self.debug:
                self.logger.debug(f"Parsed LLM response: {llm_response}")
                self.logger.debug(f"Response action type: {type(llm_response.action)}")

            if self.debug and llm_response.reasoning:
                self.logger.debug(f"Reasoning: {llm_response.reasoning}")

            # Store response in history
            self.history.append(llm_response)
            self.prompt_renderer.add_to_history(llm_response)

            # Track if this was a parsing error
            if llm_response.is_default:
                self.logger.error(f"Error during {response} parsing, defaulting to first choice.")
                self.last_error = "LLM parsing error"
            else:
                self.last_error = None

            return llm_response.action

        except Exception as e:
            self.logger.error(f"LLM call failed: {str(e)}", exc_info=True)
            self.last_error = str(e)
            return 1  # Default to first choice

    def reset(self) -> None:
        """Reset agent state"""
        self.history = []

    def on_game_end(self, final_state: Dict[str, Any]) -> None:
        """Log final state for analysis"""
        if self.debug:
            self.logger.debug(f"Game ended with state: {final_state}")

    def __str__(self) -> str:
        """String representation of the agent"""
        return f"LLMAgent(model={self.model_name}, template={self.template}, temperature={self.temperature})"
