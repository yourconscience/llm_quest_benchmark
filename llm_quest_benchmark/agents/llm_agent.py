"""LLM agent for Space Rangers quests"""
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from json_repair import repair_json

from llm_quest_benchmark.agents.base import QuestPlayer
from llm_quest_benchmark.constants import (
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    DEFAULT_TEMPLATE,
    MODEL_CHOICES,
    SYSTEM_ROLE_TEMPLATE,
)
from llm_quest_benchmark.llm.client import get_llm_client
from llm_quest_benchmark.llm.prompt import PromptRenderer
from llm_quest_benchmark.schemas.response import LLMResponse


def _parse_json_response(response: str,
                         debug: bool = False,
                         logger: Optional[logging.Logger] = None) -> Optional[Dict[str, Any]]:
    """Try to parse response as JSON, with repair attempt if needed"""
    try:
        # Extract JSON from response if there are backticks
        if '```json' in response:
            # Find the start and end of the JSON block
            start = response.find('```json') + 7
            end = response.find('```', start)
            if end > start:
                json_str = response[start:end].strip()
                if debug and logger:
                    logger.debug(f"Extracted JSON: {json_str}")
                result = json.loads(json_str)
                if debug and logger:
                    logger.debug(f"Parsed JSON: {result}")
                return result

        # Try to parse directly
        result = json.loads(response)
        if debug and logger:
            logger.debug(f"Direct JSON parse successful: {result}")
        return result
    except json.JSONDecodeError:
        if debug and logger:
            logger.debug("Initial JSON parse failed, attempting repair")
        try:
            repaired = repair_json(response)
            if debug and logger:
                logger.debug(f"Repaired JSON: {repaired}")
            result = json.loads(repaired)
            if debug and logger:
                logger.debug(f"Parse of repaired JSON successful: {result}")
            return result
        except Exception as e:
            if debug and logger:
                logger.error(f"JSON repair failed: {e}")
            return None


def _validate_action_number(action: int,
                            num_choices: int,
                            debug: bool = False,
                            logger: Optional[logging.Logger] = None) -> bool:
    """Validate that action number is within valid range"""
    if 1 <= action <= num_choices:
        return True
    if debug and logger:
        logger.error(f"Action number {action} out of range [1, {num_choices}]")
    return False


def parse_llm_response(response: str,
                       num_choices: int,
                       debug: bool = False,
                       logger: Optional[logging.Logger] = None) -> LLMResponse:
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
                    return LLMResponse(action=action,
                                       reasoning=response_json.get('reasoning'),
                                       analysis=response_json.get('analysis'),
                                       is_default=False)
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
        logger.error(
            f"Error during response parsing, defaulting to first choice. Response: {response[:100]}..."
        )
    return LLMResponse(action=1, is_default=True)


class LLMAgent(QuestPlayer):
    """LLM-powered agent for Space Rangers quests"""

    SUPPORTED_MODELS = MODEL_CHOICES

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        system_template: str = SYSTEM_ROLE_TEMPLATE,
        action_template: str = DEFAULT_TEMPLATE,
        temperature: float = DEFAULT_TEMPERATURE,
        skip_single: bool = False,
        debug: bool = False,
        memory_config: Optional[Dict[str, Any]] = None,
        tools: Optional[List[str]] = None,
    ):
        super().__init__(skip_single=skip_single)
        self.debug = debug
        self.model_name = model_name.lower()
        self.system_template = system_template
        self.action_template = action_template
        self.temperature = temperature
        self.memory_config = memory_config or {"type": "message_history", "max_history": 10}
        self.tools = tools or []
        # Set agent_id for database records
        self.agent_id = f"llm_{self.model_name}"

        if self.model_name not in self.SUPPORTED_MODELS:
            raise ValueError(
                f"Unsupported model: {model_name}. Supported models are: {self.SUPPORTED_MODELS}")

        self.logger = logging.getLogger(self.__class__.__name__)
        if self.debug:
            self.logger.setLevel(logging.DEBUG)
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(name)s - %(message)s'))
            self.logger.addHandler(handler)

        # Initialize prompt renderer with memory configuration
        self.prompt_renderer = PromptRenderer(
            None,
            system_template=system_template,
            action_template=action_template,
            memory_config=self.memory_config
        )

        # Initialize LLM client with system prompt and temperature
        self.llm = get_llm_client(model_name,
                                  system_prompt=self.prompt_renderer.render_system_prompt(),
                                  temperature=temperature)
        self.history: List[LLMResponse] = []
        self._last_response = LLMResponse(action=1,
                                          is_default=True)  # Initialize with default response

    def get_last_response(self) -> Optional[LLMResponse]:
        """Get the last LLM response from history"""
        return self.history[-1] if self.history else self._last_response

    def _get_action_impl(self, state: str, choices: List[Dict[str, str]]) -> int:
        """Implementation of action selection logic.

        Args:
            state (str): Current game state text
            choices (List[Dict[str, str]]): List of available choices

        Returns:
            int: Selected action number (1-based)
        """
        if self.debug:
            self.logger.debug(f"Getting action for state with {len(choices)} choices available")
            for i, choice in enumerate(choices):
                self.logger.debug(f"Choice {i+1}: {choice.get('text', 'NO TEXT')}")
        try:
            # Format prompt
            prompt = self._format_prompt(state, choices)
            if self.debug:
                self.logger.debug(f"\nPrompt:\n{prompt}")

            # Get LLM response
            llm_response = self.llm.get_completion(prompt)
            if self.debug:
                self.logger.debug(f"LLM response: {llm_response}")
                choices_debug = []
                for i, c in enumerate(choices):
                    choices_debug.append(f"{i+1}: {c['text']}")
                self.logger.debug(f"Available choices: {choices_debug}")

            # Parse response
            parsed_response = parse_llm_response(llm_response, len(choices), self.debug,
                                                 self.logger)
            if self.debug:
                self.logger.debug(f"Parsed LLM response: {parsed_response}")
                self.logger.debug(f"Final action to be returned: {parsed_response.action}")

            # Store response in history
            self.history.append(parsed_response)
            self._last_response = parsed_response

            # Check that action is within valid range before returning
            if parsed_response.action < 1 or parsed_response.action > len(choices):
                self.logger.error(
                    f"INVALID ACTION DETECTED: {parsed_response.action} not in range 1-{len(choices)}"
                )
                # Use default first action instead
                parsed_response.action = 1
                self.logger.warning(f"Defaulting to action 1 instead")

            return parsed_response.action

        except Exception as e:
            self.logger.error(f"Error during LLM call: {e}")
            default_response = LLMResponse(action=1, is_default=True)
            self.history.append(default_response)
            self._last_response = default_response
            return 1  # Default to first choice on error

    def reset(self) -> None:
        """Reset agent state"""
        self.history = []
        self._last_response = LLMResponse(action=1, is_default=True)  # Reset to default response

    def on_game_start(self) -> None:
        """Called when game starts"""
        super().on_game_start()
        self._last_response = LLMResponse(action=1, is_default=True)  # Reset to default response

    def on_game_end(self, final_state: Dict[str, Any]) -> None:
        """Log final state for analysis"""
        if self.debug:
            self.logger.debug(f"Game ended with state: {final_state}")

    def __str__(self) -> str:
        """String representation of the agent"""
        return f"LLMAgent(model={self.model_name}, system_template={self.system_template}, action_template={self.action_template}, temperature={self.temperature})"

    def _format_prompt(self, state: str, choices: List[Dict[str, str]]) -> str:
        """Format the prompt for the LLM using the template renderer"""
        # Use the prompt renderer to generate formatted prompt
        # Add the state to the history for memory tracking
        self.prompt_renderer.add_to_history({'text': state, 'choices': choices})
        
        # Use the template renderer
        return self.prompt_renderer.render_action_prompt(state, choices)
    
    def handle_tool_request(self, request: str) -> str:
        """Handle tool requests
        
        Args:
            request (str): Tool request string
            
        Returns:
            str: Tool response
        """
        if "calculator" in self.tools and "calculate" in request.lower():
            return self.prompt_renderer.handle_calculator_tool(request)
        else:
            return "No tool available for this request."
