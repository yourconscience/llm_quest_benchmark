"""Tool-augmented harness implementations."""

from typing import Any

from llm_quest_benchmark.constants import DEFAULT_MODEL, DEFAULT_TEMPERATURE, SYSTEM_ROLE_TEMPLATE
from llm_quest_benchmark.harnesses.base import BaseHarness, _parse_json_response
from llm_quest_benchmark.harnesses.memory import CompactionMemory, DefaultMemory
from llm_quest_benchmark.harnesses.tools import QuestHistoryTool, Scratchpad, calculator
from llm_quest_benchmark.harnesses.trajectory import MAX_READ_COUNT, MAX_SEARCH_RESULTS, Trajectory
from llm_quest_benchmark.schemas.response import LLMResponse
from llm_quest_benchmark.schemas.state import AgentState


class ToolCompactHarness(BaseHarness):
    """Compacted-memory harness with a two-phase tool selection/action loop."""

    harness_name = "tool_compact"
    DEFAULT_HISTORY_WINDOW = 10
    MAX_TOOL_INPUT_CHARS = 500

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        system_template: str = SYSTEM_ROLE_TEMPLATE,
        action_template: str = "tool_augmented.jinja",
        temperature: float = DEFAULT_TEMPERATURE,
        skip_single: bool = False,
        debug: bool = False,
        compaction_interval: int = 50,
        memory_module=None,
        history_window: int | None = None,
        **_,
    ):
        self._step_log: list[dict[str, Any]] = []
        self._history_window = history_window or self.DEFAULT_HISTORY_WINDOW
        self._scratchpad_tool = Scratchpad()
        self._history_tool = QuestHistoryTool(self._step_log, self._history_window)
        super().__init__(
            model_name=model_name,
            system_template=system_template,
            action_template=action_template,
            temperature=temperature,
            skip_single=skip_single,
            debug=debug,
            memory_module=memory_module or CompactionMemory(compaction_interval=compaction_interval),
            tools=[calculator, self._scratchpad_tool, self._history_tool],
        )
        self._memory_mode = "compaction"
        self._compaction_interval = compaction_interval

    def _recent_steps(self) -> list[str]:
        return [
            f"Step {entry['step']}: {entry['observation']} -> {entry.get('selected_choice', 'n/a')}"
            for entry in self._step_log[-self._history_window :]
        ]

    def _tool_descriptions(self) -> list[str]:
        return [
            "quest_history(query): search earlier observations and chosen actions in this quest.",
            "calculator(expression): evaluate arithmetic and simple comparisons.",
            "scratchpad(operation, content): read or replace one persistent note. operation is read or write_replace.",
        ]

    def quest_history(self, query: str) -> str:
        return self._history_tool.search(query)

    @staticmethod
    def calculator(expression: str) -> str:
        return calculator(expression)

    def scratchpad(self, operation: str, content: str = "") -> str:
        op = (operation or "").strip().lower()
        if op == "read":
            return self._scratchpad_tool.read()
        if op == "write_replace":
            return self._scratchpad_tool.write_replace(content)
        return "error: operation must be read or write_replace"

    def _build_tool_prompt(
        self,
        observation: str,
        choices: list[dict[str, str]],
        prompt_kind: str,
        tool_results: list[str] | None = None,
    ) -> str:
        template = self.prompt_renderer.get_template(self.action_template)
        return template.render(
            prompt_kind=prompt_kind,
            observation=observation,
            choices=[{"text": choice.get("text", "")} for choice in choices],
            tool_descriptions=self._tool_descriptions(),
            tool_results=tool_results or [],
            recent_steps=self._recent_steps(),
            scratchpad_note=self._scratchpad_tool.read() if self._scratchpad_tool.read() != "(empty)" else "",
        ).strip()

    @staticmethod
    def _extract_tool_calls(response: str) -> list[dict[str, Any]]:
        payload, _ = _parse_json_response(response)
        if not isinstance(payload, dict):
            return []
        tool_calls = payload.get("tool_calls")
        if not isinstance(tool_calls, list):
            return []

        normalized = []
        for item in tool_calls[:1]:
            if not isinstance(item, dict):
                continue
            tool_name = str(item.get("tool") or "").strip()
            tool_input = item.get("input")
            operation = str(item.get("operation") or "").strip()
            content = str(item.get("content") or "").strip()
            if isinstance(tool_input, dict):
                operation = operation or str(tool_input.get("operation") or "").strip()
                content = content or str(tool_input.get("content") or "").strip()
                tool_input = tool_input.get("expression") or tool_input.get("query") or tool_input.get("content") or ""
            tool_input = str(tool_input or "").strip()
            if len(tool_input) > ToolCompactHarness.MAX_TOOL_INPUT_CHARS:
                tool_input = tool_input[: ToolCompactHarness.MAX_TOOL_INPUT_CHARS]
            if len(content) > ToolCompactHarness.MAX_TOOL_INPUT_CHARS:
                content = content[: ToolCompactHarness.MAX_TOOL_INPUT_CHARS]
            if tool_name:
                normalized.append({"tool": tool_name, "input": tool_input, "operation": operation, "content": content})
        return normalized

    def _execute_tool_calls(self, tool_calls: list[dict[str, Any]]) -> list[str]:
        results = []
        for tc in tool_calls:
            name, inp = tc["tool"], tc.get("input", "")
            if name == "quest_history":
                result = self.quest_history(inp)
            elif name == "calculator":
                result = self.calculator(inp)
            elif name == "scratchpad":
                operation = tc.get("operation") or inp
                result = self.scratchpad(str(operation), str(tc.get("content") or ""))
            else:
                result = f"unknown tool: {name}"
            call_repr = inp
            if name == "scratchpad":
                call_repr = f"{tc.get('operation') or inp}, {tc.get('content') or ''}".strip(", ")
            results.append(f"{name}({call_repr}) => {result}")
        return results

    def _final_choice(
        self,
        observation: str,
        choices: list[dict[str, str]],
        tool_results: list[str] | None = None,
    ) -> tuple[LLMResponse, dict[str, Any]]:
        prompt = self._build_tool_prompt(observation, choices, prompt_kind="final", tool_results=tool_results)
        parsed_response = self._parse_with_retries(prompt, observation, choices)
        return parsed_response, {
            "prompt_tokens": parsed_response.prompt_tokens,
            "completion_tokens": parsed_response.completion_tokens,
            "total_tokens": parsed_response.total_tokens,
            "estimated_cost_usd": parsed_response.estimated_cost_usd,
        }

    def _log_step(self, observation: str, choices: list[dict[str, str]], response: LLMResponse) -> None:
        selected = ""
        if 1 <= response.action <= len(choices):
            selected = choices[response.action - 1].get("text", "")
        clipped = " ".join((observation or "").strip().split())
        if len(clipped) > 180:
            clipped = clipped[:180] + "..."
        self._step_log.append(
            {
                "step": len(self._step_log) + 1,
                "observation": clipped,
                "choices": [c.get("text", "") for c in choices],
                "selected_choice": selected,
            }
        )

    def _get_action_impl(self, state: str, choices: list[dict[str, str]]) -> int:
        try:
            state_signature = self._state_signature(state, choices)
            contextual_state = self._build_contextual_state(state)
            self._ensure_llm()

            selection_prompt = self._build_tool_prompt(contextual_state, choices, prompt_kind="select")
            selection_response = self._call_llm(selection_prompt)
            selection_usage = self.llm.get_last_usage()
            tool_calls = self._extract_tool_calls(selection_response)
            parsed_response = self._parse_llm_response(selection_response, len(choices))
            tool_results: list[str] = []
            final_choice_used = False

            total_usage = self._normalize_usage(selection_usage)
            if tool_calls:
                tool_results = self._execute_tool_calls(tool_calls)
                parsed_response, final_usage = self._final_choice(contextual_state, choices, tool_results=tool_results)
                total_usage = self._normalize_usage(self._merge_usage(total_usage, final_usage))
                final_choice_used = True
            elif parsed_response.is_default:
                parsed_response, final_usage = self._final_choice(contextual_state, choices, tool_results=[])
                total_usage = self._normalize_usage(self._merge_usage(total_usage, final_usage))
                final_choice_used = True

            if not final_choice_used:
                action_before_policy = parsed_response.action
                parsed_response.action = self._apply_safety_filter(choices, parsed_response.action)
                if parsed_response.action != action_before_policy and not parsed_response.reasoning:
                    parsed_response.reasoning = "policy_safety_override"

            parsed_response.prompt_tokens = total_usage["prompt_tokens"]
            parsed_response.completion_tokens = total_usage["completion_tokens"]
            parsed_response.total_tokens = total_usage["total_tokens"]
            parsed_response.estimated_cost_usd = total_usage["estimated_cost_usd"]
            parsed_response.tool_calls = tool_calls or None
            parsed_response.tool_results = tool_results or None

            self.history.append(parsed_response)
            self._last_response = parsed_response
            self._remember_decision(state, choices, state_signature, parsed_response)
            self._log_step(state, choices, parsed_response)
            return parsed_response.action
        except Exception as exc:
            self.logger.error("Tool harness error during LLM call: %s", exc)
            default_response = LLMResponse(
                action=1,
                is_default=True,
                parse_mode="error_default",
                reasoning=f"tool_harness_error: {exc}",
            )
            self.history.append(default_response)
            self._last_response = default_response
            return 1

    def reset(self) -> None:
        super().reset()
        self._step_log = []
        self._scratchpad_tool.reset()
        self._history_tool.step_log = self._step_log


class ToolHintedHarness(ToolCompactHarness):
    harness_name = "tool_hinted"

    def __init__(self, *args, action_template: str = "tool_augmented_hints.jinja", **kwargs):
        super().__init__(*args, action_template=action_template, **kwargs)


class ProgrammaticMemoryHarness(ToolCompactHarness):
    """Bounded recent-context harness with full-fidelity history_read/history_search.

    Subclasses ToolCompactHarness to reuse its tool-select-then-act call budget
    (`_build_tool_prompt`, `_final_choice`, `_get_action_impl`) unchanged, which is
    what keeps "at most one retrieval call" a structural property rather than a
    duplicated invariant. Memory, tool set, and step bookkeeping are overridden:
    this harness carries no compaction and no clipped step log. `DefaultMemory`
    is the single bounded recent-context source in the prompt; the trajectory
    is an on-demand retrieval view of the canonical `AgentState` objects emitted
    by the runner after each executed decision.
    """

    harness_name = "programmatic_memory"

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        system_template: str = SYSTEM_ROLE_TEMPLATE,
        action_template: str = "programmatic_memory.jinja",
        temperature: float = DEFAULT_TEMPERATURE,
        skip_single: bool = False,
        debug: bool = False,
        memory_module=None,
        **_,
    ):
        self._trajectory = Trajectory()
        self._scratchpad_tool = Scratchpad()
        # Bypass ToolCompactHarness.__init__: it wires CompactionMemory and the
        # quest_history tool, both of which this harness intentionally replaces.
        BaseHarness.__init__(
            self,
            model_name=model_name,
            system_template=system_template,
            action_template=action_template,
            temperature=temperature,
            skip_single=skip_single,
            debug=debug,
            memory_module=memory_module or DefaultMemory(),
            tools=[calculator, self._scratchpad_tool, self._trajectory],
        )

    def on_step(self, agent_state: AgentState) -> None:
        """Index the runner's canonical executed decision for retrieval."""
        self._trajectory.append(agent_state)

    def _tool_descriptions(self) -> list[str]:
        return [
            "history_read(start_step, count): read a consecutive range of full earlier steps "
            f"by step number (up to {MAX_READ_COUNT} steps per call, fewer if very long steps "
            "hit the character budget; the result says how many were shown).",
            "history_search(query, limit): literal case-insensitive search over full earlier "
            f"observations, choices, and selected choices (up to {MAX_SEARCH_RESULTS} results).",
            "calculator(expression): evaluate arithmetic and simple comparisons.",
            "scratchpad(operation, content): read or replace one persistent note. operation is read or write_replace.",
        ]

    def _recent_steps(self) -> list[str]:
        # DefaultMemory (injected into `observation` via _build_contextual_state)
        # is the single bounded recent-context source for this harness; the
        # trajectory contributes no second recent-context block, only on-demand
        # history_read/history_search retrieval.
        return []

    def history_read(self, start_step, count) -> str:
        return self._trajectory.read(start_step, count)

    def history_search(self, query, limit) -> str:
        return self._trajectory.search(query, limit)

    @staticmethod
    def _extract_tool_calls(response: str) -> list[dict[str, Any]]:
        payload, _ = _parse_json_response(response)
        if not isinstance(payload, dict):
            return []
        tool_calls = payload.get("tool_calls")
        if not isinstance(tool_calls, list):
            return []

        normalized = []
        for item in tool_calls[:1]:
            if not isinstance(item, dict):
                continue
            tool_name = str(item.get("tool") or "").strip()
            tool_input = item.get("input")
            operation = str(item.get("operation") or "").strip()
            content = str(item.get("content") or "").strip()
            start_step = item.get("start_step")
            count = item.get("count")
            limit = item.get("limit")
            if isinstance(tool_input, dict):
                operation = operation or str(tool_input.get("operation") or "").strip()
                content = content or str(tool_input.get("content") or "").strip()
                start_step = tool_input.get("start_step", start_step)
                count = tool_input.get("count", count)
                limit = tool_input.get("limit", limit)
                tool_input = tool_input.get("expression") or tool_input.get("query") or tool_input.get("content") or ""
            tool_input = str(tool_input or "").strip()
            if len(tool_input) > ProgrammaticMemoryHarness.MAX_TOOL_INPUT_CHARS:
                tool_input = tool_input[: ProgrammaticMemoryHarness.MAX_TOOL_INPUT_CHARS]
            if len(content) > ProgrammaticMemoryHarness.MAX_TOOL_INPUT_CHARS:
                content = content[: ProgrammaticMemoryHarness.MAX_TOOL_INPUT_CHARS]
            if tool_name:
                normalized.append(
                    {
                        "tool": tool_name,
                        "input": tool_input,
                        "start_step": start_step,
                        "count": count,
                        "limit": limit,
                        "operation": operation,
                        "content": content,
                    }
                )
        return normalized

    def _execute_tool_calls(self, tool_calls: list[dict[str, Any]]) -> list[str]:
        results = []
        for tc in tool_calls:
            name = tc["tool"]
            if name == "history_read":
                start_step, count = tc.get("start_step"), tc.get("count")
                result = self.history_read(start_step, count)
                call_repr = f"start_step={start_step}, count={count}"
            elif name == "history_search":
                query, limit = tc.get("input", ""), tc.get("limit")
                result = self.history_search(query, limit)
                call_repr = f"{query}, limit={limit}"
            elif name == "calculator":
                result = self.calculator(tc.get("input", ""))
                call_repr = tc.get("input", "")
            elif name == "scratchpad":
                operation = tc.get("operation") or tc.get("input", "")
                result = self.scratchpad(str(operation), str(tc.get("content") or ""))
                call_repr = f"{operation}, {tc.get('content') or ''}".strip(", ")
            else:
                result = f"unknown tool: {name}"
                call_repr = tc.get("input", "")
            results.append(f"{name}({call_repr}) => {result}")
        return results

    def _log_step(self, observation: str, choices: list[dict[str, str]], response: LLMResponse) -> None:
        # The runner emits the canonical AgentState to on_step after env.step;
        # this harness has no separate clipped step log to populate here.
        pass

    def reset(self) -> None:
        # Bypass ToolCompactHarness.reset: it clears the quest_history step log and
        # tool this harness does not have.
        BaseHarness.reset(self)
        self._trajectory.reset()
        self._scratchpad_tool.reset()
