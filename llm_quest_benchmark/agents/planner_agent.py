"""Deprecated compatibility wrapper for the planner harness."""

import warnings

from llm_quest_benchmark.harnesses.planner import PlannerHarness as PlannerAgent

warnings.warn("planner_agent is deprecated, use harnesses.planner", DeprecationWarning, stacklevel=2)

__all__ = ["PlannerAgent"]
