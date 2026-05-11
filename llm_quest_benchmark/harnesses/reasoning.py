"""Reasoning harness variants."""

from llm_quest_benchmark.constants import DEFAULT_MODEL, DEFAULT_TEMPERATURE, SYSTEM_ROLE_TEMPLATE
from llm_quest_benchmark.harnesses.memory import DefaultMemory, FullTranscriptMemory
from llm_quest_benchmark.harnesses.minimal import MinimalHarness


class ReasoningRecentHarness(MinimalHarness):
    harness_name = "reasoning_recent"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        system_template: str = SYSTEM_ROLE_TEMPLATE,
        action_template: str = "reasoning.jinja",
        temperature: float = DEFAULT_TEMPERATURE,
        skip_single: bool = False,
        debug: bool = False,
        memory_module=None,
        **kwargs,
    ):
        super().__init__(
            model_name=model_name,
            system_template=system_template,
            action_template=action_template,
            temperature=temperature,
            skip_single=skip_single,
            debug=debug,
            memory_module=memory_module or DefaultMemory(),
            **kwargs,
        )


class ReasoningFullTranscriptHarness(MinimalHarness):
    harness_name = "reasoning_full"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        system_template: str = SYSTEM_ROLE_TEMPLATE,
        action_template: str = "reasoning.jinja",
        temperature: float = DEFAULT_TEMPERATURE,
        skip_single: bool = False,
        debug: bool = False,
        memory_module=None,
        **kwargs,
    ):
        super().__init__(
            model_name=model_name,
            system_template=system_template,
            action_template=action_template,
            temperature=temperature,
            skip_single=skip_single,
            debug=debug,
            memory_module=memory_module or FullTranscriptMemory(),
            **kwargs,
        )
