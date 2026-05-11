"""Minimal harness implementation."""

from llm_quest_benchmark.constants import DEFAULT_MODEL, DEFAULT_TEMPERATURE, SYSTEM_ROLE_TEMPLATE
from llm_quest_benchmark.harnesses.base import BaseHarness
from llm_quest_benchmark.harnesses.memory import DefaultMemory
from llm_quest_benchmark.schemas.response import LLMResponse


class MinimalHarness(BaseHarness):
    """Simple prompt-call-parse action loop with recent-memory context."""

    harness_name = "minimal"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        system_template: str = SYSTEM_ROLE_TEMPLATE,
        action_template: str = "stub.jinja",
        temperature: float = DEFAULT_TEMPERATURE,
        skip_single: bool = False,
        debug: bool = False,
        memory_module=None,
        compaction_interval: int = 50,
        **_,
    ):
        del compaction_interval
        super().__init__(
            model_name=model_name,
            system_template=system_template,
            action_template=action_template,
            temperature=temperature,
            skip_single=skip_single,
            debug=debug,
            memory_module=memory_module or DefaultMemory(),
        )

    def _get_action_impl(self, observation: str, choices: list[dict[str, str]]) -> int:
        try:
            state_signature = self._state_signature(observation, choices)
            prompt = self._format_prompt(self._build_contextual_state(observation), choices)
            parsed_response = self._parse_with_retries(prompt, observation, choices)
            self.history.append(parsed_response)
            self._last_response = parsed_response
            self._remember_decision(observation, choices, state_signature, parsed_response)
            if parsed_response.action < 1 or parsed_response.action > len(choices):
                parsed_response.action = 1
            return parsed_response.action
        except Exception as exc:
            self.logger.error("Harness error during LLM call: %s", exc)
            default_response = LLMResponse(
                action=1,
                is_default=True,
                parse_mode="error_default",
                reasoning=f"llm_call_error: {exc}",
            )
            self.history.append(default_response)
            self._last_response = default_response
            return 1

    def reset(self) -> None:
        super().reset()
