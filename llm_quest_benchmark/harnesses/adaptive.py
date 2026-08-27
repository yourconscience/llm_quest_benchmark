"""Experimental adaptive-reasoning harness.

Reasoning depth is a prompt-level policy: concise by default, deep once the
state repeats or curated progress stalls. It does not depend on any
provider-specific reasoning control.
"""

from llm_quest_benchmark.constants import DEFAULT_MODEL, DEFAULT_TEMPERATURE, SYSTEM_ROLE_TEMPLATE
from llm_quest_benchmark.harnesses.base import BaseHarness
from llm_quest_benchmark.harnesses.memory import DefaultMemory
from llm_quest_benchmark.players.base import DecisionContext
from llm_quest_benchmark.schemas.records import QuestAction
from llm_quest_benchmark.schemas.response import LLMResponse

DEFAULT_ADAPTIVE_STALL_STEPS = 3
MODE_CONCISE = "concise"
MODE_DEEP = "deep"


class AdaptiveReasoningHarness(BaseHarness):
    """Recent-context harness that deepens its prompt only when triggered."""

    harness_name = "adaptive_reasoning"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        system_template: str = SYSTEM_ROLE_TEMPLATE,
        action_template: str = "adaptive_reasoning.jinja",
        temperature: float = DEFAULT_TEMPERATURE,
        skip_single: bool = False,
        debug: bool = False,
        adaptive_stall_steps: int | None = None,
        memory_module=None,
        **_,
    ):
        super().__init__(
            model_name=model_name,
            system_template=system_template,
            action_template=action_template,
            temperature=temperature,
            skip_single=skip_single,
            debug=debug,
            memory_module=memory_module or DefaultMemory(),
        )
        self.adaptive_stall_steps = (
            int(adaptive_stall_steps) if adaptive_stall_steps is not None else DEFAULT_ADAPTIVE_STALL_STEPS
        )
        self.reasoning_mode = MODE_CONCISE
        self._context = DecisionContext()

    def reset(self) -> None:
        super().reset()
        self.reasoning_mode = MODE_CONCISE
        self._context = DecisionContext()

    def get_quest_action(
        self,
        observation: str,
        choices: list[dict[str, str]],
        context: DecisionContext,
    ) -> QuestAction:
        self._context = context
        return super().get_quest_action(observation, choices, context)

    def _select_mode(self, state_signature: str) -> tuple[str, str | None]:
        """Pick the reasoning mode and the trigger that caused it.

        Recovery is implicit: once neither trigger holds the next decision goes
        back to concise mode while all decision history is retained.
        """
        if self._state_action_counts.get(state_signature):
            return MODE_DEEP, "repeated_state"
        stalled = int(self._context.progress.stalled_transitions)
        if stalled >= self.adaptive_stall_steps:
            return MODE_DEEP, f"progress_stalled_{stalled}"
        return MODE_CONCISE, None

    def _build_prompt(self, observation: str, choices: list[dict[str, str]], mode: str, trigger: str | None) -> str:
        template = self.prompt_renderer.get_template(self.action_template)
        return template.render(
            observation=observation,
            choices=[{"text": choice.get("text", "")} for choice in choices],
            mode=mode,
            trigger=trigger,
            progress=self._context.progress.current,
        ).strip()

    def _get_action_impl(self, observation: str, choices: list[dict[str, str]]) -> int:
        try:
            state_signature = self._state_signature(observation, choices)
            mode, trigger = self._select_mode(state_signature)
            self.reasoning_mode = mode

            contextual_state = self._build_contextual_state(observation)
            prompt = self._build_prompt(contextual_state, choices, mode, trigger)
            parsed_response = self._parse_with_retries(prompt, observation, choices)
            if parsed_response.action < 1 or parsed_response.action > len(choices):
                parsed_response.action = 1

            self.history.append(parsed_response)
            self._last_response = parsed_response
            self._remember_decision(observation, choices, state_signature, parsed_response)
            return parsed_response.action
        except Exception as exc:
            self.logger.error("Adaptive reasoning harness error during LLM call: %s", exc)
            default_response = LLMResponse(
                action=1,
                is_default=True,
                parse_mode="error_default",
                reasoning=f"adaptive_reasoning_error: {exc}",
            )
            self.history.append(default_response)
            self._last_response = default_response
            return 1
