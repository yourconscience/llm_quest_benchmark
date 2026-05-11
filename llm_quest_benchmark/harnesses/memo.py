"""Compacted-memory harness variants."""

from llm_quest_benchmark.constants import DEFAULT_MODEL, DEFAULT_TEMPERATURE, SYSTEM_ROLE_TEMPLATE
from llm_quest_benchmark.harnesses.memory import CompactionMemory
from llm_quest_benchmark.harnesses.minimal import MinimalHarness


class MemoCompactHarness(MinimalHarness):
    harness_name = "memo_compact"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        system_template: str = SYSTEM_ROLE_TEMPLATE,
        action_template: str = "stateful_compact.jinja",
        temperature: float = DEFAULT_TEMPERATURE,
        skip_single: bool = False,
        debug: bool = False,
        compaction_interval: int = 50,
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
            memory_module=memory_module or CompactionMemory(compaction_interval=compaction_interval),
            **kwargs,
        )
        self._memory_mode = "compaction"
        self._compaction_interval = compaction_interval


class HintedCompactHarness(MemoCompactHarness):
    harness_name = "hinted_compact"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        system_template: str = SYSTEM_ROLE_TEMPLATE,
        action_template: str = "stateful_compact_hints.jinja",
        temperature: float = DEFAULT_TEMPERATURE,
        skip_single: bool = False,
        debug: bool = False,
        compaction_interval: int = 50,
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
            compaction_interval=compaction_interval,
            memory_module=memory_module,
            **kwargs,
        )


class CompactionNoMemoHarness(MemoCompactHarness):
    """Retired Exp 4 ablation: compacted transcript without memo-oriented prompting."""

    harness_name = "compaction_no_memo"

    def __init__(self, *args, action_template: str = "reasoning.jinja", **kwargs):
        super().__init__(*args, action_template=action_template, **kwargs)


class MemoExtendedHarness(MemoCompactHarness):
    """Retired Exp 4 variant with a larger generic memo field."""

    harness_name = "memo_extended"

    def __init__(self, *args, action_template: str = "memo_extended.jinja", **kwargs):
        super().__init__(*args, action_template=action_template, **kwargs)


class MemoStructuredHarness(MemoCompactHarness):
    """Retired Exp 4 variant with structured memo prompting."""

    harness_name = "memo_structured"

    def __init__(self, *args, action_template: str = "memo_structured.jinja", **kwargs):
        super().__init__(*args, action_template=action_template, **kwargs)


class MemoCotHarness(MemoCompactHarness):
    """Retired Exp 4 variant with scratchpad-style memo prompting."""

    harness_name = "memo_cot"

    def __init__(self, *args, action_template: str = "memo_cot.jinja", **kwargs):
        super().__init__(*args, action_template=action_template, **kwargs)
