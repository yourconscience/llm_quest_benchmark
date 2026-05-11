"""Base harness class for quest benchmark experiments."""

import hashlib
import json
import logging
import re
from abc import abstractmethod
from typing import Any

from json_repair import repair_json

from llm_quest_benchmark.agents.base import QuestPlayer
from llm_quest_benchmark.constants import DEFAULT_TEMPLATE, normalize_template_name
from llm_quest_benchmark.llm.client import get_llm_client, parse_model_name
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


def _parse_json_response(
    response: str,
    debug: bool = False,
    logger: logging.Logger | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Try to parse response as JSON, with repair attempt if needed."""
    cleaned_response = (response or "").strip()
    if not cleaned_response:
        return None, None

    try:
        if "```json" in cleaned_response:
            start = cleaned_response.find("```json") + 7
            end = cleaned_response.find("```", start)
            if end > start:
                json_str = cleaned_response[start:end].strip()
                if debug and logger:
                    logger.debug("Extracted JSON: %s", json_str)
                result = json.loads(json_str)
                if debug and logger:
                    logger.debug("Parsed JSON: %s", result)
                return result, "json_fenced"

        embedded_json = re.search(r"\{[\s\S]*\}", cleaned_response)
        if embedded_json:
            candidate = embedded_json.group(0).strip()
            if candidate and candidate != cleaned_response:
                try:
                    result = json.loads(candidate)
                    if debug and logger:
                        logger.debug("Parsed embedded JSON: %s", result)
                    return result, "json_embedded"
                except json.JSONDecodeError:
                    pass

        result = json.loads(cleaned_response)
        if debug and logger:
            logger.debug("Direct JSON parse successful: %s", result)
        return result, "json_direct"
    except json.JSONDecodeError:
        if debug and logger:
            logger.debug("Initial JSON parse failed, attempting repair")
        try:
            repaired = repair_json(cleaned_response)
            if debug and logger:
                logger.debug("Repaired JSON: %s", repaired)
            result = json.loads(repaired)
            if debug and logger:
                logger.debug("Parse of repaired JSON successful: %s", result)
            return result, "json_repaired"
        except Exception as exc:
            if debug and logger:
                logger.error("JSON repair failed: %s", exc)
            return None, None


def _validate_action_number(
    action: int,
    num_choices: int,
    debug: bool = False,
    logger: logging.Logger | None = None,
) -> bool:
    """Validate that action number is within valid range."""
    if 1 <= action <= num_choices:
        return True
    if debug and logger:
        logger.error("Action number %s out of range [1, %s]", action, num_choices)
    return False


def _extract_action_from_text(response: str, num_choices: int) -> int | None:
    """Extract a candidate action from free-form text."""
    for match in re.finditer(r"\b(\d+)\b", response):
        action = int(match.group(1))
        if 1 <= action <= num_choices:
            return action
    return None


def _extract_field_from_text(response: str, field: str) -> str | None:
    """Best-effort extraction of analysis/reasoning from loosely formatted output."""
    if not response:
        return None

    json_pattern = re.compile(
        rf"""['"]{re.escape(field)}['"]\s*:\s*['"](?P<value>.*?)['"]""",
        re.IGNORECASE | re.DOTALL,
    )
    match = json_pattern.search(response)
    if match:
        value = " ".join(match.group("value").strip().split())
        if value:
            return value

    partial_json_pattern = re.compile(
        rf"""['"]{re.escape(field)}['"]\s*:\s*['"](?P<value>[^"\n\r]+)""",
        re.IGNORECASE,
    )
    match = partial_json_pattern.search(response)
    if match:
        value = " ".join(match.group("value").strip().split())
        if value:
            return value

    label_pattern = re.compile(
        rf"""(?im)^\s*{re.escape(field)}\s*[:\-]\s*(?P<value>.+?)\s*$""",
    )
    match = label_pattern.search(response)
    if match:
        value = " ".join(match.group("value").strip().split())
        if value:
            return value

    return None


def _raw_reasoning_fallback(response: str) -> str | None:
    compact = " ".join((response or "").strip().split())
    if not compact:
        return None
    if len(compact) > 240:
        compact = compact[:237] + "..."
    return f"raw_response: {compact}"


def _is_numeric_raw_reasoning(reasoning: str | None) -> bool:
    if not reasoning or not reasoning.startswith("raw_response:"):
        return False
    payload = reasoning.split(":", 1)[1].strip()
    return payload.isdigit()


def parse_llm_response(
    response: str,
    num_choices: int,
    debug: bool = False,
    logger: logging.Logger | None = None,
) -> LLMResponse:
    """Parse an LLM response and return a structured response object."""
    if debug and logger:
        logger.debug("Raw LLM response: %s", response)

    extracted_analysis = _extract_field_from_text(response, "analysis")
    extracted_reasoning = _extract_field_from_text(response, "reasoning")
    raw_reasoning = _raw_reasoning_fallback(response)

    response_json, json_parse_mode = _parse_json_response(response, debug, logger)
    if response_json and isinstance(response_json, dict):
        analysis = response_json.get("analysis") or extracted_analysis
        reasoning = response_json.get("reasoning") or response_json.get("thinking") or extracted_reasoning
        if not reasoning and analysis:
            reasoning = analysis
        if not analysis and not reasoning:
            reasoning = raw_reasoning

        memo_raw = response_json.get("memo")
        memo = str(memo_raw) if memo_raw is not None else None
        action_value = response_json.get("action") or response_json.get("result") or response_json.get("choice")
        if action_value is not None:
            try:
                action = int(action_value)
                if _validate_action_number(action, num_choices, debug, logger):
                    return LLMResponse(
                        action=action,
                        reasoning=reasoning,
                        analysis=analysis,
                        memo=memo,
                        is_default=False,
                        parse_mode=json_parse_mode or "json",
                    )
            except (ValueError, TypeError):
                if debug and logger:
                    logger.error("Invalid action value in JSON: %s", action_value)

    try:
        action = int(response.strip())
        if _validate_action_number(action, num_choices, debug, logger):
            return LLMResponse(
                action=action,
                reasoning=extracted_reasoning or extracted_analysis or raw_reasoning,
                analysis=extracted_analysis,
                is_default=False,
                parse_mode="number_only",
            )
    except ValueError:
        if debug and logger:
            logger.error("Could not parse response as number: %s", response)

    extracted_action = _extract_action_from_text(response, num_choices)
    if extracted_action is not None:
        return LLMResponse(
            action=extracted_action,
            reasoning=extracted_reasoning or extracted_analysis or raw_reasoning,
            analysis=extracted_analysis,
            is_default=False,
            parse_mode="number_extracted",
        )

    if debug and logger:
        logger.error("Error during response parsing, defaulting to first choice. Response: %s...", response[:100])
    return LLMResponse(
        action=1,
        reasoning=extracted_reasoning or extracted_analysis or raw_reasoning,
        analysis=extracted_analysis,
        is_default=True,
        parse_mode="default_first",
    )


class BaseHarness(QuestPlayer):
    """Abstract LLM harness base class."""

    def __init__(
        self,
        model_name,
        system_template,
        temperature,
        skip_single,
        debug,
        memory_module=None,
        tools=None,
        action_template=DEFAULT_TEMPLATE,
    ):
        super().__init__(skip_single=skip_single)
        self.debug = debug
        self.model_name = model_name.lower()
        self.system_template = normalize_template_name(system_template)
        self.action_template = normalize_template_name(action_template)
        self.temperature = temperature
        self.harness_name = getattr(self.__class__, "harness_name", "")
        self.agent_id = f"harness_{self.model_name}"
        self.memory_module = memory_module
        self.tools = tools or []
        self.model_spec = parse_model_name(self.model_name)
        self.logger = logging.getLogger(self.__class__.__name__)
        if self.debug:
            self.logger.setLevel(logging.DEBUG)
            self.logger.propagate = False
            if not any(getattr(h, "_llm_quest_handler", False) for h in self.logger.handlers):
                handler = logging.StreamHandler()
                handler.setFormatter(logging.Formatter("%(name)s - %(message)s"))
                handler._llm_quest_handler = True
                self.logger.addHandler(handler)

        self.prompt_renderer = PromptRenderer(
            None,
            system_template=self.system_template,
            action_template=self.action_template,
        )
        self.llm = None
        self.history: list[LLMResponse] = []
        self._use_safety_filter = True
        self._last_response = LLMResponse(action=1, is_default=True)
        self._observation_history: list[str] = []
        self._decision_history: list[dict[str, Any]] = []
        self._state_action_counts: dict[str, dict[int, int]] = {}
        self._step_count = 0

    def _ensure_llm(self) -> None:
        """Lazily create the provider client only when inference is needed."""
        if self.llm is None:
            self.llm = get_llm_client(
                self.model_name,
                system_prompt=self.prompt_renderer.render_system_prompt(),
                temperature=self.temperature,
            )

    @abstractmethod
    def _get_action_impl(self, observation, choices) -> int:
        """Return the selected 1-based action number."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset harness state between episodes."""
        super().reset()
        self.history = []
        self._last_response = LLMResponse(action=1, is_default=True)
        self._observation_history = []
        self._decision_history = []
        self._state_action_counts = {}
        self._step_count = 0
        if self.memory_module is not None:
            self.memory_module.reset()

    def get_action(self, observation: str, choices: list[dict[str, str]]) -> int:
        clean = (observation or "").strip()
        if clean:
            self._observation_history.append(clean)
            if len(self._observation_history) > 20:
                self._observation_history = self._observation_history[-20:]
            if self.memory_module is not None:
                self.memory_module.update({"observation": clean, "step": self._step_count + 1})
        return super().get_action(observation, choices)

    def on_game_start(self) -> None:
        super().on_game_start()
        self.reset()

    def on_game_end(self, final_state: dict[str, Any]) -> None:
        if self.debug:
            self.logger.debug("Game ended with state: %s", final_state)

    def get_last_response(self) -> LLMResponse | None:
        return self._last_response

    @property
    def _quest_briefing(self) -> str | None:
        return getattr(self.memory_module, "_quest_briefing", None)

    @_quest_briefing.setter
    def _quest_briefing(self, value: str | None) -> None:
        if self.memory_module is not None:
            self.memory_module._quest_briefing = value

    @property
    def _transcript(self) -> list[dict[str, Any]]:
        return getattr(self.memory_module, "_transcript", [])

    @_transcript.setter
    def _transcript(self, value: list[dict[str, Any]]) -> None:
        if self.memory_module is not None:
            self.memory_module._transcript = value

    @property
    def _steps_since_compaction(self) -> int:
        return getattr(self.memory_module, "_steps_since_compaction", 0)

    @_steps_since_compaction.setter
    def _steps_since_compaction(self, value: int) -> None:
        if self.memory_module is not None:
            self.memory_module._steps_since_compaction = value

    def _build_contextual_state(self, state: str) -> str:
        if self.memory_module is None:
            return state
        context = self.memory_module.get_context(self._step_count + 1)
        if not context:
            return state
        return f"{context}\n\nCurrent story state:\n{state}"

    @staticmethod
    def _normalize_for_signature(value: str, max_len: int = 320) -> str:
        text = (value or "").lower()
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_len] if len(text) > max_len else text

    def _state_signature(self, state: str, choices: list[dict[str, str]]) -> str:
        normalized_state = self._normalize_for_signature(state, max_len=420)
        normalized_choices = "|".join(
            self._normalize_for_signature(choice.get("text", ""), max_len=110) for choice in choices
        )
        raw_signature = f"{normalized_state}||{normalized_choices}"
        return hashlib.sha1(raw_signature.encode("utf-8", errors="ignore")).hexdigest()[:20]

    def _remember_decision(
        self,
        state: str,
        choices: list[dict[str, str]],
        state_signature: str,
        response: LLMResponse,
    ) -> None:
        action = int(response.action)
        counts = self._state_action_counts.setdefault(state_signature, {})
        counts[action] = counts.get(action, 0) + 1

        selected_text = ""
        if 1 <= action <= len(choices):
            selected_text = choices[action - 1].get("text", "")
        state_snippet = (state or "").strip()
        if len(state_snippet) > 220:
            state_snippet = state_snippet[:220] + "..."

        decision = {
            "state": state_snippet,
            "action": action,
            "choice": selected_text,
            "choice_text": selected_text,
            "parse_mode": response.parse_mode or "unknown",
            "memo": (response.memo or "").strip()[:350] or None,
            "reasoning": (response.reasoning or "")[:800],
        }
        self._decision_history.append(decision)
        if len(self._decision_history) > 40:
            self._decision_history = self._decision_history[-40:]

        self._step_count += 1
        if self.memory_module is not None:
            self.memory_module.update(
                {
                    "step": self._step_count,
                    "observation": state,
                    "choices": [c.get("text", "") for c in choices],
                    **decision,
                }
            )

    def _format_prompt(self, observation, choices, memo=None, context=None) -> str:
        """Render system and action Jinja templates for the current decision."""
        system_prompt = self.prompt_renderer.render_system_prompt(
            observation=observation,
            choices=choices,
            memo=memo,
            context=context,
        ).strip()
        action_prompt = self.prompt_renderer.action_template.render(
            observation=observation,
            choices=[{"text": c.get("text", "")} for c in choices],
            memo=memo,
            context=context,
        ).strip()
        if system_prompt:
            return f"{system_prompt}\n\n{action_prompt}".strip()
        return action_prompt

    def _parse_llm_response(self, response, num_choices) -> LLMResponse:
        """Parse an LLM response into a structured response object."""
        return parse_llm_response(response, num_choices, self.debug, self.logger)

    def _call_llm(self, prompt, system_prompt=None) -> str:
        """Call the LLM client with lightweight retry handling."""
        self._ensure_llm()
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                if system_prompt is not None:
                    return self.llm.get_completion(prompt, system_prompt=system_prompt)
                return self.llm.get_completion(prompt)
            except TypeError:
                if system_prompt is not None:
                    return self.llm.get_completion(prompt)
                raise
            except Exception as exc:
                last_error = exc
                if self.debug:
                    self.logger.warning("LLM call failed on attempt %d: %s", attempt + 1, exc)
        raise last_error or RuntimeError("LLM call failed")

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

    def _apply_safety_filter(self, choices, preferred_action) -> int:
        """Replace obviously risky actions when a clearly safer alternative exists."""
        if not self._use_safety_filter or len(choices) < 2:
            return preferred_action

        current_idx = preferred_action - 1
        if current_idx < 0 or current_idx >= len(choices):
            return preferred_action

        scored = [(idx + 1, self._choice_risk_score(c.get("text", ""))) for idx, c in enumerate(choices)]
        scored.sort(key=lambda item: item[1])

        best_action, best_score = scored[0]
        current_score = self._choice_risk_score(choices[current_idx].get("text", ""))
        if current_score - best_score >= 2:
            if self.debug:
                self.logger.debug(
                    "Safety filter override: %s -> %s (risk %s -> %s)",
                    preferred_action,
                    best_action,
                    current_score,
                    best_score,
                )
            return best_action
        return preferred_action

    @staticmethod
    def _normalize_usage(usage: dict[str, Any] | None) -> dict[str, Any]:
        usage = usage or {}
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))
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
    def _merge_usage(cls, first: dict[str, Any] | None, second: dict[str, Any] | None) -> dict[str, Any]:
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

    def _format_retry_prompt(self, state: str, choices: list[dict[str, str]]) -> str:
        clipped_state = (state or "").strip()
        if len(clipped_state) > 500:
            clipped_state = clipped_state[:500] + "..."
        choices_text = "\n".join([f"{i + 1}. {(c.get('text', '') or '')[:160]}" for i, c in enumerate(choices)])
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

    def _format_force_numeric_retry_prompt(self, choices: list[dict[str, str]]) -> str:
        choices_text = "\n".join([f"{i + 1}. {(c.get('text', '') or '')[:110]}" for i, c in enumerate(choices)])
        return f"""Pick one action number.
{choices_text}
Reply with one integer only: 1 to {len(choices)}."""

    def _needs_force_numeric_retry(self) -> bool:
        return self.model_spec.provider == "openai" and (
            self.model_spec.model_id.startswith("gpt-5") or self.model_spec.model_id.startswith("o")
        )

    def _parse_with_retries(self, prompt: str, observation: str, choices: list[dict[str, str]]) -> LLMResponse:
        """Call the model, parse, and retry once on invalid/default output."""
        llm_response = self._call_llm(prompt)
        llm_usage = self.llm.get_last_usage()
        first_response = self._parse_llm_response(llm_response, len(choices))
        parsed_response = first_response

        if parsed_response.is_default:
            retry_response = self._call_llm(self._format_retry_prompt(observation, choices))
            retry_usage = self.llm.get_last_usage()
            llm_usage = self._merge_usage(llm_usage, retry_usage)
            retry_parsed = self._parse_llm_response(retry_response, len(choices))
            if not retry_parsed.is_default:
                retry_parsed.parse_mode = f"retry_{retry_parsed.parse_mode or 'parsed'}"
                parsed_response = retry_parsed
            elif self._needs_force_numeric_retry():
                force_retry_response = self._call_llm(self._format_force_numeric_retry_prompt(choices))
                force_retry_usage = self.llm.get_last_usage()
                llm_usage = self._merge_usage(llm_usage, force_retry_usage)
                force_retry_parsed = self._parse_llm_response(force_retry_response, len(choices))
                if not force_retry_parsed.is_default:
                    force_retry_parsed.parse_mode = f"force_retry_{force_retry_parsed.parse_mode or 'parsed'}"
                    parsed_response = force_retry_parsed

        if parsed_response is not first_response:
            if parsed_response.analysis is None and first_response.analysis is not None:
                parsed_response.analysis = first_response.analysis
            if _is_numeric_raw_reasoning(parsed_response.reasoning):
                if first_response.reasoning and not _is_numeric_raw_reasoning(first_response.reasoning):
                    parsed_response.reasoning = first_response.reasoning
                else:
                    first_raw_reasoning = _raw_reasoning_fallback(llm_response)
                    if first_raw_reasoning and not _is_numeric_raw_reasoning(first_raw_reasoning):
                        parsed_response.reasoning = first_raw_reasoning

        action_before_policy = parsed_response.action
        parsed_response.action = self._apply_safety_filter(choices, parsed_response.action)
        if parsed_response.action != action_before_policy and not parsed_response.reasoning:
            parsed_response.reasoning = "policy_safety_override"

        usage_payload = self._normalize_usage(llm_usage)
        parsed_response.prompt_tokens = usage_payload["prompt_tokens"]
        parsed_response.completion_tokens = usage_payload["completion_tokens"]
        parsed_response.total_tokens = usage_payload["total_tokens"]
        parsed_response.estimated_cost_usd = usage_payload["estimated_cost_usd"]
        return parsed_response
