"""Deprecated compatibility wrapper for the tool harness."""

import warnings

from llm_quest_benchmark.harnesses.tool_harness import ToolCompactHarness as ToolAgent

warnings.warn("tool_agent is deprecated, use harnesses.tool_harness", DeprecationWarning, stacklevel=2)

__all__ = ["ToolAgent"]
