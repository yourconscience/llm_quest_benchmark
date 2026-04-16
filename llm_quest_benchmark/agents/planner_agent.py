"""Planner agent with a lightweight plan-maintain-act loop."""
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from llm_quest_benchmark.agents.llm_agent import LLMAgent, LLMResponse, parse_llm_response

RESOURCE_CHANGE_PATTERN = re.compile(
    r"\b\d+\s*(?:cr|credits|fuel|hp|health|ammo|energy|supplies)\b",
    re.IGNORECASE,
)
UNEXPECTED_CHANGE_KEYWORDS = (
    "new location",
    "location",
    "sector",
    "planet",
    "station",
    "base",
    "arrive",
    "arrived",
    "entered",
    "failure",
    "failed",
    "alarm",
    "damage",
    "damaged",
    "wounded",
    "injured",
    "fuel",
    "credits",
    "resource",
    "supplies",
)


class PlannerAgent(LLMAgent):
    """LLM agent that maintains a short plan and re-plans on notable changes."""

    def __init__(
        self,
        *args,
        action_template: str = "planner.jinja",
        **kwargs,
    ):
        super().__init__(*args, action_template=action_template, **kwargs)
        self.agent_id = f"planner_{self.model_name}"
        self.current_plan: Optional[str] = None
        self._plan_history: List[str] = []

    def _recent_actions(self) -> List[str]:
        entries = []
        for item in self._decision_history[-3:]:
            choice = (item.get("choice") or "").strip()
            if not choice:
                continue
            entries.append(f"{item.get('action')}. {choice}")
        return entries

    @staticmethod
    def _normalize_plan(raw_plan: str) -> str:
        compact = " ".join((raw_plan or "").strip().split())
        if not compact:
            return ""

        sentences = re.split(r"(?<=[.!?])\s+", compact)
        sentences = [sentence.strip() for sentence in sentences if sentence.strip()]
        if len(sentences) >= 5:
            return " ".join(sentences[:5])
        return compact

    def _build_planner_prompt(
        self,
        observation: str,
        choices: List[Dict[str, str]],
        prompt_kind: str,
        replan_reason: Optional[str] = None,
    ) -> str:
        template = self.prompt_renderer.get_template(self.action_template)
        return template.render(
            prompt_kind=prompt_kind,
            observation=observation,
            choices=[{"text": choice.get("text", "")} for choice in choices],
            current_plan=self.current_plan,
            replan_reason=replan_reason,
            recent_actions=self._recent_actions(),
        ).strip()

    def _has_unexpected_change(self, observation: str) -> bool:
        if len(self._observation_history) < 2:
            return False

        previous = self._observation_history[-2].lower()
        current = (observation or "").lower()
        current_resources = set(RESOURCE_CHANGE_PATTERN.findall(current))
        previous_resources = set(RESOURCE_CHANGE_PATTERN.findall(previous))
        if current_resources != previous_resources and current_resources:
            return True

        for keyword in UNEXPECTED_CHANGE_KEYWORDS:
            if keyword in current and keyword not in previous:
                return True
        return False

    def _should_replan(self, observation: str, state_signature: str) -> Tuple[bool, Optional[str]]:
        if not self.current_plan:
            return True, "No plan exists yet."

        if any(self._state_action_counts.get(state_signature, {}).values()):
            return True, "This state has repeated, so a previous action already failed to progress."

        if self._has_unexpected_change(observation):
            return True, "The observation introduced a new location, failure signal, or resource change."

        return False, None

    def _update_plan(
        self,
        observation: str,
        choices: List[Dict[str, str]],
        replan_reason: Optional[str],
    ) -> Dict[str, Any]:
        self._ensure_llm()
        prompt = self._build_planner_prompt(
            observation,
            choices,
            prompt_kind="plan",
            replan_reason=replan_reason,
        )
        plan_response = self.llm.get_completion(prompt)
        usage = self.llm.get_last_usage()
        plan = self._normalize_plan(plan_response)
        if not plan:
            if self.current_plan:
                plan = self.current_plan
            else:
                plan = (
                    "Gather clues, protect resources, and avoid obvious traps while "
                    "advancing toward the main objective."
                )
        self.current_plan = plan
        self._plan_history.append(plan)
        if len(self._plan_history) > 10:
            self._plan_history = self._plan_history[-10:]
        return usage

    def _choose_action_with_plan(
        self,
        observation: str,
        choices: List[Dict[str, str]],
        replan_reason: Optional[str],
    ) -> Tuple[LLMResponse, Dict[str, Any]]:
        prompt = self._build_planner_prompt(
            observation,
            choices,
            prompt_kind="act",
            replan_reason=replan_reason,
        )
        llm_response = self.llm.get_completion(prompt)
        llm_usage = self.llm.get_last_usage()
        parsed_response = parse_llm_response(llm_response, len(choices), self.debug, self.logger)

        if parsed_response.is_default:
            retry_response = self.llm.get_completion(self._format_retry_prompt(observation, choices))
            retry_usage = self.llm.get_last_usage()
            llm_usage = self._merge_usage(llm_usage, retry_usage)
            retry_parsed = parse_llm_response(
                retry_response,
                len(choices),
                self.debug,
                self.logger,
            )
            if not retry_parsed.is_default:
                retry_parsed.parse_mode = f"retry_{retry_parsed.parse_mode or 'parsed'}"
                parsed_response = retry_parsed
            elif self._needs_force_numeric_retry():
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
                    force_retry_parsed.parse_mode = (
                        f"force_retry_{force_retry_parsed.parse_mode or 'parsed'}"
                    )
                    parsed_response = force_retry_parsed

        return parsed_response, llm_usage

    def _get_action_impl(self, state: str, choices: List[Dict[str, str]]) -> int:
        if self.debug:
            self.logger.debug("PlannerAgent evaluating state with %s choices", len(choices))
        try:
            state_signature = self._state_signature(state, choices)
            should_replan, replan_reason = self._should_replan(state, state_signature)
            plan_usage = None
            if should_replan:
                plan_usage = self._update_plan(state, choices, replan_reason)

            parsed_response, action_usage = self._choose_action_with_plan(
                state,
                choices,
                replan_reason if should_replan else None,
            )
            action_before_policy = parsed_response.action
            parsed_response.action = self._apply_safety_filter(parsed_response.action, choices)
            if parsed_response.action != action_before_policy and not parsed_response.reasoning:
                parsed_response.reasoning = "policy_safety_override"

            loop_adjusted_action = self._apply_loop_breaker(
                parsed_response.action,
                state_signature,
                choices,
            )
            if loop_adjusted_action != parsed_response.action:
                parsed_response.action = loop_adjusted_action
                parsed_response.reasoning = (
                    (parsed_response.reasoning + "; " if parsed_response.reasoning else "")
                    + "policy_loop_break_override"
                )

            total_usage = (
                self._merge_usage(plan_usage, action_usage) if plan_usage else self._normalize_usage(action_usage)
            )
            if plan_usage:
                total_usage = self._normalize_usage(total_usage)

            parsed_response.prompt_tokens = total_usage["prompt_tokens"]
            parsed_response.completion_tokens = total_usage["completion_tokens"]
            parsed_response.total_tokens = total_usage["total_tokens"]
            parsed_response.estimated_cost_usd = total_usage["estimated_cost_usd"]

            self.history.append(parsed_response)
            self._last_response = parsed_response
            self._remember_decision(state, choices, state_signature, parsed_response)

            if parsed_response.action < 1 or parsed_response.action > len(choices):
                self.logger.error(
                    "INVALID ACTION DETECTED: %s not in range 1-%s",
                    parsed_response.action,
                    len(choices),
                )
                parsed_response.action = 1

            return parsed_response.action
        except Exception as exc:
            self.logger.error("Planner agent error during LLM call: %s", exc)
            default_response = LLMResponse(
                action=1,
                is_default=True,
                parse_mode="error_default",
                reasoning=f"planner_error: {exc}",
            )
            self.history.append(default_response)
            self._last_response = default_response
            return 1

    def reset(self) -> None:
        super().reset()
        self.current_plan = None
        self._plan_history = []

    def on_game_start(self) -> None:
        super().on_game_start()
        self.current_plan = None
        self._plan_history = []

    def on_game_end(self, final_state: Dict[str, Any]) -> None:
        if self.debug:
            logging.getLogger(self.__class__.__name__).debug(
                "Planner finished with plan: %s", self.current_plan
            )
        super().on_game_end(final_state)
