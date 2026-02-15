"""LLM agent for Space Rangers quests"""
import json
import logging
import re
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
from llm_quest_benchmark.llm.client import (
    get_llm_client,
    is_supported_model_name,
    parse_model_name,
)
from llm_quest_benchmark.llm.prompt import PromptRenderer
from llm_quest_benchmark.schemas.response import LLMResponse

RISKY_CHOICE_KEYWORDS = (
    "улететь",
    "сдаться",
    "отказ",
    "провал",
    "убежать",
    "surrender",
    "give up",
)

SAFE_CHOICE_KEYWORDS = (
    "пройти мимо",
    "избежать",
    "подготов",
    "библиотек",
    "изуч",
    "wait",
    "avoid",
    "study",
)


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


def _extract_action_from_text(response: str, num_choices: int) -> Optional[int]:
    """Extract a candidate action from free-form text."""
    for match in re.finditer(r"\b(\d+)\b", response):
        action = int(match.group(1))
        if 1 <= action <= num_choices:
            return action
    return None


def _extract_field_from_text(response: str, field: str) -> Optional[str]:
    """Best-effort extraction of analysis/reasoning from loosely formatted output."""
    if not response:
        return None

    # JSON-like field forms: "analysis": "...", 'analysis': '...'
    json_pattern = re.compile(
        rf"""['"]{re.escape(field)}['"]\s*:\s*['"](?P<value>.*?)['"]""",
        re.IGNORECASE | re.DOTALL,
    )
    match = json_pattern.search(response)
    if match:
        value = " ".join(match.group("value").strip().split())
        if value:
            return value

    # Partial JSON field forms without a closing quote in truncated outputs.
    partial_json_pattern = re.compile(
        rf"""['"]{re.escape(field)}['"]\s*:\s*['"](?P<value>[^"\n\r]+)""",
        re.IGNORECASE,
    )
    match = partial_json_pattern.search(response)
    if match:
        value = " ".join(match.group("value").strip().split())
        if value:
            return value

    # Label forms: Analysis: ..., Reasoning - ...
    label_pattern = re.compile(
        rf"""(?im)^\s*{re.escape(field)}\s*[:\-]\s*(?P<value>.+?)\s*$""",
    )
    match = label_pattern.search(response)
    if match:
        value = " ".join(match.group("value").strip().split())
        if value:
            return value

    return None


def _raw_reasoning_fallback(response: str) -> Optional[str]:
    compact = " ".join((response or "").strip().split())
    if not compact:
        return None
    if len(compact) > 240:
        compact = compact[:237] + "..."
    return f"raw_response: {compact}"


def _is_numeric_raw_reasoning(reasoning: Optional[str]) -> bool:
    if not reasoning:
        return False
    if not reasoning.startswith("raw_response:"):
        return False
    payload = reasoning.split(":", 1)[1].strip()
    return payload.isdigit()


def parse_llm_response(response: str,
                       num_choices: int,
                       debug: bool = False,
                       logger: Optional[logging.Logger] = None) -> LLMResponse:
    """Parse LLM response and return structured response object."""
    if debug and logger:
        logger.debug(f"Raw LLM response: {response}")

    extracted_analysis = _extract_field_from_text(response, "analysis")
    extracted_reasoning = _extract_field_from_text(response, "reasoning")
    raw_reasoning = _raw_reasoning_fallback(response)

    # Try parsing as JSON first
    response_json = _parse_json_response(response, debug, logger)
    if response_json and isinstance(response_json, dict):
        analysis = response_json.get("analysis") or extracted_analysis
        reasoning = response_json.get("reasoning") or extracted_reasoning
        if not reasoning and analysis:
            reasoning = analysis
        if not analysis and not reasoning:
            reasoning = raw_reasoning

        # Check for either 'action' or 'result' field
        action_value = (
            response_json.get('action')
            or response_json.get('result')
            or response_json.get('choice')
        )
        if action_value is not None:
            try:
                action = int(action_value)
                if _validate_action_number(action, num_choices, debug, logger):
                    return LLMResponse(action=action,
                                       reasoning=reasoning,
                                       analysis=analysis,
                                       is_default=False)
            except (ValueError, TypeError):
                if debug and logger:
                    logger.error(f"Invalid action value in JSON: {action_value}")

    # Try parsing as plain number
    try:
        action = int(response.strip())
        if _validate_action_number(action, num_choices, debug, logger):
            return LLMResponse(
                action=action,
                reasoning=extracted_reasoning or extracted_analysis or raw_reasoning,
                analysis=extracted_analysis,
                is_default=False,
            )
    except ValueError:
        if debug and logger:
            logger.error(f"Could not parse response as number: {response}")

    # Fallback: extract first valid integer from text.
    extracted_action = _extract_action_from_text(response, num_choices)
    if extracted_action is not None:
        return LLMResponse(
            action=extracted_action,
            reasoning=extracted_reasoning or extracted_analysis or raw_reasoning,
            analysis=extracted_analysis,
            is_default=False,
        )

    # Default to first choice if all parsing attempts fail
    if debug and logger:
        logger.error(
            f"Error during response parsing, defaulting to first choice. Response: {response[:100]}..."
        )
    return LLMResponse(
        action=1,
        reasoning=extracted_reasoning or extracted_analysis or raw_reasoning,
        analysis=extracted_analysis,
        is_default=True,
    )


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
    ):
        super().__init__(skip_single=skip_single)
        self.debug = debug
        self.model_name = model_name.lower()
        self.system_template = system_template
        self.action_template = action_template
        self.temperature = temperature
        # Set agent_id for database records
        self.agent_id = f"llm_{self.model_name}"

        if not is_supported_model_name(self.model_name):
            raise ValueError(
                f"Unsupported model: {model_name}. Supported models are: {self.SUPPORTED_MODELS}")

        self.model_spec = parse_model_name(self.model_name)
        self.logger = logging.getLogger(self.__class__.__name__)
        if self.debug:
            self.logger.setLevel(logging.DEBUG)
            self.logger.propagate = False
            if not any(getattr(h, "_llm_quest_handler", False) for h in self.logger.handlers):
                handler = logging.StreamHandler()
                handler.setFormatter(logging.Formatter('%(name)s - %(message)s'))
                handler._llm_quest_handler = True
                self.logger.addHandler(handler)

        # Initialize prompt renderer
        self.prompt_renderer = PromptRenderer(None,
                                              system_template=system_template,
                                              action_template=action_template)

        # Delay API client creation so template-only flows and tests do not require API keys.
        self.llm = None
        self.history: List[LLMResponse] = []
        self._observation_history: List[str] = []
        self._context_window = 3
        self._context_chars = 220
        self._use_safety_filter = True
        self._last_response = LLMResponse(action=1,
                                          is_default=True)  # Initialize with default response

    def _ensure_llm(self):
        """Lazily create the provider client only when inference is needed."""
        if self.llm is None:
            self.llm = get_llm_client(
                self.model_name,
                system_prompt=self.prompt_renderer.render_system_prompt(),
                temperature=self.temperature,
            )

    def get_last_response(self) -> Optional[LLMResponse]:
        """Get the last LLM response from history"""
        return self._last_response

    def get_action(self, observation: str, choices: List[Dict[str, str]]) -> int:
        """Track observation history for context, then delegate base action flow."""
        self._remember_observation(observation)
        return super().get_action(observation, choices)

    def _remember_observation(self, observation: str) -> None:
        clean = (observation or "").strip()
        if not clean:
            return
        self._observation_history.append(clean)
        if len(self._observation_history) > 20:
            self._observation_history = self._observation_history[-20:]

    def _build_contextual_state(self, state: str) -> str:
        """Add a compact previous-step context window for better local decisions."""
        if len(self._observation_history) <= 1:
            return state

        previous = self._observation_history[:-1][-self._context_window:]
        if not previous:
            return state

        snippets = []
        for idx, text in enumerate(previous, start=1):
            clipped = text if len(text) <= self._context_chars else text[:self._context_chars] + "..."
            snippets.append(f"[Previous {idx}] {clipped}")

        context_block = "\n\n".join(snippets)
        return f"Recent context from previous steps:\n{context_block}\n\n{state}"

    def _choice_risk_score(self, choice_text: str) -> int:
        text = (choice_text or "").lower()
        score = 0
        for keyword in RISKY_CHOICE_KEYWORDS:
            if keyword in text:
                score += 2
        for keyword in SAFE_CHOICE_KEYWORDS:
            if keyword in text:
                score -= 1
        return score

    def _apply_safety_filter(self, action: int, choices: List[Dict[str, str]]) -> int:
        """Replace obviously risky actions when a clearly safer alternative exists."""
        if not self._use_safety_filter or len(choices) < 2:
            return action

        current_idx = action - 1
        if current_idx < 0 or current_idx >= len(choices):
            return action

        scored = [(idx + 1, self._choice_risk_score(c.get("text", "")))
                  for idx, c in enumerate(choices)]
        scored.sort(key=lambda item: item[1])

        best_action, best_score = scored[0]
        current_score = self._choice_risk_score(choices[current_idx].get("text", ""))

        # Only override when the chosen action is materially riskier than the best option.
        if current_score - best_score >= 2:
            if self.debug:
                self.logger.debug(
                    "Safety filter override: %s -> %s (risk %s -> %s)",
                    action,
                    best_action,
                    current_score,
                    best_score,
                )
            return best_action
        return action

    @staticmethod
    def _normalize_usage(usage: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        usage = usage or {}
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        total_tokens = int(
            usage.get("total_tokens")
            or (prompt_tokens + completion_tokens)
        )
        estimated_cost_usd = usage.get("estimated_cost_usd")
        if estimated_cost_usd is not None:
            estimated_cost_usd = float(estimated_cost_usd)
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": estimated_cost_usd,
        }

    @classmethod
    def _merge_usage(cls, first: Optional[Dict[str, Any]], second: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        a = cls._normalize_usage(first)
        b = cls._normalize_usage(second)
        merged_cost = None
        if a["estimated_cost_usd"] is not None or b["estimated_cost_usd"] is not None:
            merged_cost = (a["estimated_cost_usd"] or 0.0) + (b["estimated_cost_usd"] or 0.0)
        return {
            "prompt_tokens": a["prompt_tokens"] + b["prompt_tokens"],
            "completion_tokens": a["completion_tokens"] + b["completion_tokens"],
            "total_tokens": a["total_tokens"] + b["total_tokens"],
            "estimated_cost_usd": merged_cost,
        }

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
            prompt = self._format_prompt(self._build_contextual_state(state), choices)
            if self.debug:
                self.logger.debug(f"\nPrompt:\n{prompt}")

            # Get LLM response
            self._ensure_llm()
            llm_response = self.llm.get_completion(prompt)
            llm_usage = self.llm.get_last_usage()
            if self.debug:
                self.logger.debug(f"LLM response: {llm_response}")
                choices_debug = []
                for i, c in enumerate(choices):
                    choices_debug.append(f"{i+1}: {c['text']}")
                self.logger.debug(f"Available choices: {choices_debug}")

            # Parse response
            first_response = parse_llm_response(
                llm_response,
                len(choices),
                self.debug,
                self.logger,
            )
            parsed_response = first_response

            if parsed_response.is_default:
                retry_response = self.llm.get_completion(self._format_retry_prompt(state, choices))
                retry_usage = self.llm.get_last_usage()
                llm_usage = self._merge_usage(llm_usage, retry_usage)
                retry_parsed = parse_llm_response(retry_response, len(choices), self.debug,
                                                  self.logger)
                if not retry_parsed.is_default:
                    parsed_response = retry_parsed
                elif self._needs_force_numeric_retry():
                    # GPT-5/o models occasionally return empty visible text on long prompts.
                    # Use a tiny final retry that asks for number-only output.
                    force_retry_response = self.llm.get_completion(
                        self._format_force_numeric_retry_prompt(choices)
                    )
                    force_retry_usage = self.llm.get_last_usage()
                    llm_usage = self._merge_usage(llm_usage, force_retry_usage)
                    force_retry_parsed = parse_llm_response(
                        force_retry_response,
                        len(choices),
                        self.debug,
                        self.logger,
                    )
                    if not force_retry_parsed.is_default:
                        parsed_response = force_retry_parsed

            if parsed_response is not first_response:
                if parsed_response.analysis is None and first_response.analysis is not None:
                    parsed_response.analysis = first_response.analysis
                if _is_numeric_raw_reasoning(parsed_response.reasoning):
                    if first_response.reasoning and not _is_numeric_raw_reasoning(
                        first_response.reasoning
                    ):
                        parsed_response.reasoning = first_response.reasoning
                    else:
                        first_raw_reasoning = _raw_reasoning_fallback(llm_response)
                        if first_raw_reasoning and not _is_numeric_raw_reasoning(
                            first_raw_reasoning
                        ):
                            parsed_response.reasoning = first_raw_reasoning

            parsed_response.action = self._apply_safety_filter(parsed_response.action, choices)
            usage_payload = self._normalize_usage(llm_usage)
            parsed_response.prompt_tokens = usage_payload["prompt_tokens"]
            parsed_response.completion_tokens = usage_payload["completion_tokens"]
            parsed_response.total_tokens = usage_payload["total_tokens"]
            parsed_response.estimated_cost_usd = usage_payload["estimated_cost_usd"]

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
            error_reason = _raw_reasoning_fallback(f"llm_call_error: {e}")
            default_response = LLMResponse(
                action=1,
                reasoning=error_reason,
                is_default=True,
            )
            self.history.append(default_response)
            self._last_response = default_response
            return 1  # Default to first choice on error

    def reset(self) -> None:
        """Reset agent state"""
        self.history = []
        self._observation_history = []
        self._last_response = LLMResponse(action=1, is_default=True)  # Reset to default response

    def on_game_start(self) -> None:
        """Called when game starts"""
        super().on_game_start()
        self._observation_history = []
        self._last_response = LLMResponse(action=1, is_default=True)  # Reset to default response

    def on_game_end(self, final_state: Dict[str, Any]) -> None:
        """Log final state for analysis"""
        if self.debug:
            self.logger.debug(f"Game ended with state: {final_state}")

    def __str__(self) -> str:
        """String representation of the agent"""
        return f"LLMAgent(model={self.model_name}, system_template={self.system_template}, action_template={self.action_template}, temperature={self.temperature})"

    def _format_prompt(self, state: str, choices: List[Dict[str, str]]) -> str:
        """Format the prompt for the LLM"""
        return self.prompt_renderer.render_action_prompt(state, choices).strip()

    def _format_retry_prompt(self, state: str, choices: List[Dict[str, str]]) -> str:
        """Fallback prompt that still preserves reasoning for log analysis."""
        clipped_state = (state or "").strip()
        if len(clipped_state) > 500:
            clipped_state = clipped_state[:500] + "..."
        choices_text = "\n".join([
            f"{i+1}. {(c.get('text', '') or '')[:160]}"
            for i, c in enumerate(choices)
        ])
        return f"""Choose the best action.
State: {clipped_state}
Actions:
{choices_text}

Return valid JSON only:
{{
  "analysis": "<max 25 words>",
  "reasoning": "<max 25 words>",
  "result": <integer from 1 to {len(choices)}>
}}"""

    def _format_force_numeric_retry_prompt(self, choices: List[Dict[str, str]]) -> str:
        """Very short retry prompt used for models that return empty visible output."""
        choices_text = "\n".join([
            f"{i+1}. {(c.get('text', '') or '')[:110]}"
            for i, c in enumerate(choices)
        ])
        return f"""Pick one action number.
{choices_text}
Reply with one integer only: 1 to {len(choices)}."""

    def _needs_force_numeric_retry(self) -> bool:
        return self.model_spec.provider == "openai" and (
            self.model_spec.model_id.startswith("gpt-5")
            or self.model_spec.model_id.startswith("o")
        )
