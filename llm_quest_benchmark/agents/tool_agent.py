"""Tool-augmented agent with lightweight structured prompting."""

import ast
import re
from typing import Any

from llm_quest_benchmark.agents.llm_agent import (
    LLMAgent,
    LLMResponse,
    _parse_json_response,
    parse_llm_response,
)


class ToolAgent(LLMAgent):
    """LLM agent with generic run-local tools for history, math, and state notes."""

    DEFAULT_HISTORY_WINDOW = 10
    MAX_SCRATCHPAD_CHARS = 1200
    MAX_TOOL_INPUT_CHARS = 500

    def __init__(
        self,
        *args,
        action_template: str = "tool_augmented.jinja",
        history_window: int | None = None,
        **kwargs,
    ):
        super().__init__(*args, action_template=action_template, **kwargs)
        self.agent_id = f"tool_{self.model_name}"
        self._step_log: list[dict[str, Any]] = []
        self._history_window = history_window or self.DEFAULT_HISTORY_WINDOW
        self._scratchpad = ""

    def _recent_steps(self) -> list[str]:
        snippets = []
        for entry in self._step_log[-self._history_window :]:
            snippets.append(f"Step {entry['step']}: {entry['observation']} -> {entry.get('selected_choice', 'n/a')}")
        return snippets

    def _tool_descriptions(self) -> list[str]:
        return [
            "quest_history(query): search earlier observations and chosen actions in this quest.",
            "calculator(expression): evaluate arithmetic and simple comparisons.",
            "scratchpad(operation, content): read or replace one persistent note. operation is read or write_replace.",
        ]

    def quest_history(self, query: str) -> str:
        """Return relevant previous steps from this quest run via keyword match."""
        if not self._step_log:
            return "No prior quest steps recorded yet."

        tokens = set(re.findall(r"[a-zA-Z\u0400-\u04ff0-9_]{3,}", (query or "").lower()))
        scored = []
        for entry in self._step_log:
            haystack = " ".join(
                [
                    entry.get("observation", ""),
                    " ".join(entry.get("choices", [])),
                    entry.get("selected_choice", ""),
                ]
            ).lower()
            score = sum(1 for token in tokens if token in haystack)
            scored.append((score, entry))

        scored.sort(key=lambda item: (item[0], item[1].get("step", 0)), reverse=True)
        best = [entry for s, entry in scored if s > 0][: self._history_window]
        if not best:
            best = [entry for _, entry in scored[-self._history_window :]]

        lines = []
        for entry in best:
            lines.append(
                f"Step {entry['step']}: obs={entry['observation']} | "
                f"choices={'; '.join(entry['choices'])} | picked={entry.get('selected_choice', 'n/a')}"
            )
        return "\n".join(lines)

    @staticmethod
    def calculator(expression: str) -> str:
        """Evaluate a restricted arithmetic/comparison expression."""
        expr = (expression or "").strip()
        if not expr:
            return "error: empty expression"
        if len(expr) > 240:
            return "error: expression too long"
        if not re.fullmatch(r"[0-9a-zA-Z\s+\-*/().,<>=!%]+", expr):
            return "error: unsupported characters"

        allowed_nodes = (
            ast.Expression,
            ast.Constant,
            ast.UnaryOp,
            ast.UAdd,
            ast.USub,
            ast.BinOp,
            ast.Add,
            ast.Sub,
            ast.Mult,
            ast.Div,
            ast.FloorDiv,
            ast.Mod,
            ast.Pow,
            ast.Compare,
            ast.Eq,
            ast.NotEq,
            ast.Lt,
            ast.LtE,
            ast.Gt,
            ast.GtE,
            ast.BoolOp,
            ast.And,
            ast.Or,
        )
        try:
            tree = ast.parse(expr, mode="eval")
            for node in ast.walk(tree):
                if not isinstance(node, allowed_nodes):
                    return f"error: unsupported expression element {node.__class__.__name__}"
                if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float, bool)):
                    return "error: constants must be numeric or boolean"
            result = ToolAgent._eval_calculator_node(tree.body)
        except Exception as exc:
            return f"error: {exc}"
        return f"{expr} = {result}"

    @staticmethod
    def _eval_calculator_node(node: ast.AST) -> int | float | bool:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float, bool)):
            return node.value
        if isinstance(node, ast.UnaryOp):
            value = ToolAgent._eval_calculator_node(node.operand)
            if isinstance(node.op, ast.UAdd):
                return +value
            if isinstance(node.op, ast.USub):
                return -value
        if isinstance(node, ast.BinOp):
            left = ToolAgent._eval_calculator_node(node.left)
            right = ToolAgent._eval_calculator_node(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.FloorDiv):
                return left // right
            if isinstance(node.op, ast.Mod):
                return left % right
            if isinstance(node.op, ast.Pow):
                if abs(right) > 8:
                    raise ValueError("exponent too large")
                return left**right
        if isinstance(node, ast.BoolOp):
            values = [bool(ToolAgent._eval_calculator_node(value)) for value in node.values]
            if isinstance(node.op, ast.And):
                return all(values)
            if isinstance(node.op, ast.Or):
                return any(values)
        if isinstance(node, ast.Compare):
            left = ToolAgent._eval_calculator_node(node.left)
            for op, comparator in zip(node.ops, node.comparators, strict=True):
                right = ToolAgent._eval_calculator_node(comparator)
                if isinstance(op, ast.Eq):
                    ok = left == right
                elif isinstance(op, ast.NotEq):
                    ok = left != right
                elif isinstance(op, ast.Lt):
                    ok = left < right
                elif isinstance(op, ast.LtE):
                    ok = left <= right
                elif isinstance(op, ast.Gt):
                    ok = left > right
                elif isinstance(op, ast.GtE):
                    ok = left >= right
                else:
                    raise ValueError("unsupported comparison")
                if not ok:
                    return False
                left = right
            return True
        raise ValueError("unsupported expression")

    def scratchpad(self, operation: str, content: str = "") -> str:
        """Read or replace one persistent free-form note blob."""
        op = (operation or "").strip().lower()
        if op == "read":
            return self._scratchpad or "(empty)"
        if op == "write_replace":
            note = " ".join((content or "").strip().split())
            self._scratchpad = note[: self.MAX_SCRATCHPAD_CHARS]
            return f"updated: {self._scratchpad or '(empty)'}"
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
            scratchpad_note=self._scratchpad,
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
            if len(tool_input) > ToolAgent.MAX_TOOL_INPUT_CHARS:
                tool_input = tool_input[: ToolAgent.MAX_TOOL_INPUT_CHARS]
            if len(content) > ToolAgent.MAX_TOOL_INPUT_CHARS:
                content = content[: ToolAgent.MAX_TOOL_INPUT_CHARS]
            if tool_name:
                normalized.append(
                    {
                        "tool": tool_name,
                        "input": tool_input,
                        "operation": operation,
                        "content": content,
                    }
                )
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
        prompt = self._build_tool_prompt(
            observation,
            choices,
            prompt_kind="final",
            tool_results=tool_results,
        )
        llm_response = self.llm.get_completion(prompt)
        llm_usage = self.llm.get_last_usage()
        parsed_response = parse_llm_response(llm_response, len(choices), self.debug, self.logger)

        if parsed_response.is_default:
            retry_response = self.llm.get_completion(self._format_retry_prompt(observation, choices))
            retry_usage = self.llm.get_last_usage()
            llm_usage = self._merge_usage(llm_usage, retry_usage)
            retry_parsed = parse_llm_response(retry_response, len(choices), self.debug, self.logger)
            if not retry_parsed.is_default:
                retry_parsed.parse_mode = f"retry_{retry_parsed.parse_mode or 'parsed'}"
                parsed_response = retry_parsed
            elif self._needs_force_numeric_retry():
                force_response = self.llm.get_completion(self._format_force_numeric_retry_prompt(choices))
                force_usage = self.llm.get_last_usage()
                llm_usage = self._merge_usage(llm_usage, force_usage)
                force_parsed = parse_llm_response(force_response, len(choices), self.debug, self.logger)
                if not force_parsed.is_default:
                    force_parsed.parse_mode = f"force_retry_{force_parsed.parse_mode or 'parsed'}"
                    parsed_response = force_parsed

        return parsed_response, llm_usage

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
            selection_response = self.llm.get_completion(selection_prompt)
            selection_usage = self.llm.get_last_usage()
            tool_calls = self._extract_tool_calls(selection_response)
            parsed_response = parse_llm_response(selection_response, len(choices), self.debug, self.logger)
            tool_results: list[str] = []

            total_usage = self._normalize_usage(selection_usage)
            if tool_calls:
                tool_results = self._execute_tool_calls(tool_calls)
                parsed_response, final_usage = self._final_choice(contextual_state, choices, tool_results=tool_results)
                total_usage = self._normalize_usage(self._merge_usage(total_usage, final_usage))
            elif parsed_response.is_default:
                parsed_response, final_usage = self._final_choice(contextual_state, choices, tool_results=[])
                total_usage = self._normalize_usage(self._merge_usage(total_usage, final_usage))

            action_before_policy = parsed_response.action
            parsed_response.action = self._apply_safety_filter(parsed_response.action, choices)
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
            self.logger.error("Tool agent error during LLM call: %s", exc)
            default_response = LLMResponse(
                action=1,
                is_default=True,
                parse_mode="error_default",
                reasoning=f"tool_agent_error: {exc}",
            )
            self.history.append(default_response)
            self._last_response = default_response
            return 1

    def reset(self) -> None:
        super().reset()
        self._step_log = []
        self._scratchpad = ""

    def on_game_start(self) -> None:
        super().on_game_start()
        self._step_log = []
        self._scratchpad = ""
