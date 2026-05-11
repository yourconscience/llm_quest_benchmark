"""Deprecated compatibility wrapper for harness-based LLM agents."""

import warnings

from llm_quest_benchmark.constants import (
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    DEFAULT_TEMPLATE,
    MODEL_CHOICES,
    SYSTEM_ROLE_TEMPLATE,
)
from llm_quest_benchmark.harnesses.base import (
    RISKY_CHOICE_KEYWORDS,
    SAFE_CHOICE_KEYWORDS,
    _is_numeric_raw_reasoning,
    _parse_json_response,
    _raw_reasoning_fallback,
    parse_llm_response,
)
from llm_quest_benchmark.harnesses.memory import CompactionMemory, DefaultMemory, FullTranscriptMemory
from llm_quest_benchmark.harnesses.minimal import MinimalHarness

warnings.warn("llm_agent is deprecated, use llm_quest_benchmark.harnesses", DeprecationWarning, stacklevel=2)


class LLMAgent(MinimalHarness):
    """Backward-compatible LLMAgent facade backed by concrete harness classes."""

    SUPPORTED_MODELS = MODEL_CHOICES

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        system_template: str = SYSTEM_ROLE_TEMPLATE,
        action_template: str = DEFAULT_TEMPLATE,
        temperature: float = DEFAULT_TEMPERATURE,
        skip_single: bool = False,
        debug: bool = False,
        memory_mode: str = "default",
        compaction_interval: int = 10,
    ):
        if memory_mode == "default":
            memory_module = DefaultMemory()
        elif memory_mode == "full_transcript":
            memory_module = FullTranscriptMemory()
        elif memory_mode == "compaction":
            memory_module = CompactionMemory(compaction_interval=compaction_interval)
        else:
            raise ValueError(f"Invalid memory_mode: {memory_mode}")

        super().__init__(
            model_name=model_name,
            system_template=system_template,
            action_template=action_template,
            temperature=temperature,
            skip_single=skip_single,
            debug=debug,
            memory_module=memory_module,
        )
        self.agent_id = f"llm_{self.model_name}"
        self._memory_mode = memory_mode
        self._compaction_interval = compaction_interval

    def _remember_observation(self, observation: str) -> None:
        """Compatibility hook used by legacy tests and callers."""
        clean = (observation or "").strip()
        if not clean:
            return
        self._observation_history.append(clean)
        if len(self._observation_history) > 20:
            self._observation_history = self._observation_history[-20:]
        if self.memory_module is not None:
            self.memory_module.update({"observation": clean, "step": self._step_count + 1})

    def _build_contextual_state(self, state: str) -> str:
        """Build context while honoring legacy direct history mutation."""
        if isinstance(self.memory_module, DefaultMemory):
            self.memory_module._observations = list(self._observation_history)
            self.memory_module._decisions = list(self._decision_history)
        return super()._build_contextual_state(state)

    def _apply_safety_filter(self, action_or_choices, choices_or_action) -> int:
        """Accept both legacy (action, choices) and harness (choices, action) argument order."""
        if isinstance(action_or_choices, list):
            return super()._apply_safety_filter(action_or_choices, choices_or_action)
        return super()._apply_safety_filter(choices_or_action, action_or_choices)

    def __str__(self) -> str:
        return (
            f"LLMAgent(model={self.model_name}, system_template={self.system_template}, "
            f"action_template={self.action_template}, temperature={self.temperature})"
        )


__all__ = [
    "LLMAgent",
    "parse_llm_response",
    "_parse_json_response",
    "_raw_reasoning_fallback",
    "_is_numeric_raw_reasoning",
    "RISKY_CHOICE_KEYWORDS",
    "SAFE_CHOICE_KEYWORDS",
]
