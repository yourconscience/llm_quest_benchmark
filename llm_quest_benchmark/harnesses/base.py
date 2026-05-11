"""Base harness class for quest benchmark experiments."""

import logging
from abc import abstractmethod
from typing import Any

from llm_quest_benchmark.agents.base import QuestPlayer
from llm_quest_benchmark.agents.llm_agent import (
    RISKY_CHOICE_KEYWORDS,
    SAFE_CHOICE_KEYWORDS,
    _is_numeric_raw_reasoning,
    _raw_reasoning_fallback,
    parse_llm_response,
)
from llm_quest_benchmark.constants import DEFAULT_TEMPLATE, normalize_template_name
from llm_quest_benchmark.llm.client import get_llm_client, parse_model_name
from llm_quest_benchmark.llm.prompt import PromptRenderer
from llm_quest_benchmark.schemas.response import LLMResponse


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
    ):
        super().__init__(skip_single=skip_single)
        self.debug = debug
        self.model_name = model_name.lower()
        self.system_template = normalize_template_name(system_template)
        self.action_template = DEFAULT_TEMPLATE
        self.temperature = temperature
        self.harness_name = ""
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
        if self.memory_module is not None:
            self.memory_module.reset()

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
