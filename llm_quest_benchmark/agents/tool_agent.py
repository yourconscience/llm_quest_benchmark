"""Tool-augmented agent with lightweight structured prompting."""
import ast
import operator
import re
from typing import Any, Dict, List, Optional, Tuple

from llm_quest_benchmark.agents.llm_agent import (
    LLMAgent,
    LLMResponse,
    _parse_json_response,
    parse_llm_response,
)

SAFE_AST_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
SAFE_AST_UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
DOMAIN_KNOWLEDGE = {
    "loops": "Repeated scenes usually mean a loop. Change tactics instead of replaying the same choice.",
    "resources": "Track fuel, credits, supplies, and health cues. Conservative resource choices often keep more endings reachable.",
    "npcs": "NPC dialogue often hides the safest route. Ask questions and reuse explicit hints before gambling.",
    "combat": "Aggressive combat choices are often traps unless the text clearly says you have an advantage.",
    "exploration": "Exploration choices are best when they reveal clues or new branches without abandoning the mission.",
    "traps": "Surrender, giving up, or rushing into danger can be instant-failure traps in Space Rangers quests.",
}


def calculator(expression: str) -> str:
    """Safely evaluate a simple arithmetic expression."""
    try:
        tree = ast.parse((expression or "").strip(), mode="eval")
    except SyntaxError as exc:
        return f"calculator error: invalid expression ({exc.msg})"

    def _eval(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in SAFE_AST_OPERATORS:
            return SAFE_AST_OPERATORS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in SAFE_AST_UNARY_OPERATORS:
            return SAFE_AST_UNARY_OPERATORS[type(node.op)](_eval(node.operand))
        raise ValueError(f"unsupported expression node: {type(node).__name__}")

    try:
        return str(_eval(tree))
    except Exception as exc:
        return f"calculator error: {exc}"


def domain_lookup(topic: str) -> str:
    """Return the most relevant static Space Rangers quest hint."""
    query = (topic or "").lower()
    if not query:
        return DOMAIN_KNOWLEDGE["exploration"]

    for key, value in DOMAIN_KNOWLEDGE.items():
        if key in query:
            return value

    if any(keyword in query for keyword in ("fight", "attack", "weapon", "battle")):
        return DOMAIN_KNOWLEDGE["combat"]
    if any(keyword in query for keyword in ("money", "credit", "fuel", "resource", "supply")):
        return DOMAIN_KNOWLEDGE["resources"]
    if any(keyword in query for keyword in ("talk", "npc", "merchant", "captain", "contact")):
        return DOMAIN_KNOWLEDGE["npcs"]
    if any(keyword in query for keyword in ("loop", "repeat", "again")):
        return DOMAIN_KNOWLEDGE["loops"]
    return DOMAIN_KNOWLEDGE["traps"]


class ToolAgent(LLMAgent):
    """LLM agent that can call simple local tools before choosing an action."""

    def __init__(
        self,
        *args,
        action_template: str = "tool_augmented.jinja",
        **kwargs,
    ):
        super().__init__(*args, action_template=action_template, **kwargs)
        self.agent_id = f"tool_{self.model_name}"
        self._memory_entries: List[Dict[str, Any]] = []

    def quest_memory(self, query: str) -> str:
        """Return the most relevant previous steps from this quest run."""
        if not self._memory_entries:
            return "No prior quest steps recorded yet."

        tokens = set(re.findall(r"[a-zA-Zа-яА-Я0-9_]{3,}", (query or "").lower()))
        scored_entries = []
        for entry in self._memory_entries:
            haystack = " ".join(
                [
                    entry.get("observation", ""),
                    " ".join(entry.get("choices", [])),
                    entry.get("selected_choice", ""),
                ]
            ).lower()
            score = sum(1 for token in tokens if token in haystack)
            scored_entries.append((score, entry))

        scored_entries.sort(
            key=lambda item: (
                item[0],
                item[1].get("step", 0),
            ),
            reverse=True,
        )
        best_entries = [entry for score, entry in scored_entries if score > 0][:2]
        if not best_entries:
            best_entries = [entry for _, entry in scored_entries[:2]]

        lines = []
        for entry in best_entries:
            lines.append(
                f"Step {entry['step']}: obs={entry['observation']} | "
                f"choices={'; '.join(entry['choices'])} | picked={entry.get('selected_choice', 'n/a')}"
            )
        return "\n".join(lines)

    def _tool_descriptions(self) -> List[str]:
        return [
            "calculator(expression): evaluate arithmetic for resources or tradeoffs.",
            "quest_memory(query): search earlier observations and chosen actions in this quest.",
            "domain_lookup(topic): retrieve a short Space Rangers quest heuristic.",
        ]

    def _recent_memory(self) -> List[str]:
        snippets = []
        for entry in self._memory_entries[-3:]:
            snippets.append(
                f"Step {entry['step']}: {entry['observation']} -> {entry.get('selected_choice', 'n/a')}"
            )
        return snippets

    def _build_tool_prompt(
        self,
        observation: str,
        choices: List[Dict[str, str]],
        prompt_kind: str,
        tool_results: Optional[List[str]] = None,
    ) -> str:
        template = self.prompt_renderer.get_template(self.action_template)
        return template.render(
            prompt_kind=prompt_kind,
            observation=observation,
            choices=[{"text": choice.get("text", "")} for choice in choices],
            tool_descriptions=self._tool_descriptions(),
            tool_results=tool_results or [],
            recent_memory=self._recent_memory(),
        ).strip()

    @staticmethod
    def _extract_tool_calls(response: str) -> List[Dict[str, str]]:
        payload, _ = _parse_json_response(response)
        if not isinstance(payload, dict):
            return []

        tool_calls = payload.get("tool_calls")
        if not isinstance(tool_calls, list):
            return []

        normalized = []
        for item in tool_calls[:2]:
            if not isinstance(item, dict):
                continue
            tool_name = str(item.get("tool") or "").strip()
            tool_input = str(item.get("input") or "").strip()
            if tool_name and tool_input:
                normalized.append({"tool": tool_name, "input": tool_input})
        return normalized

    def _execute_tool_calls(self, tool_calls: List[Dict[str, str]]) -> List[str]:
        tool_results = []
        for tool_call in tool_calls[:2]:
            tool_name = tool_call["tool"]
            tool_input = tool_call["input"]
            if tool_name == "calculator":
                result = calculator(tool_input)
            elif tool_name == "quest_memory":
                result = self.quest_memory(tool_input)
            elif tool_name == "domain_lookup":
                result = domain_lookup(tool_input)
            else:
                result = f"unknown tool: {tool_name}"
            tool_results.append(f"{tool_name}({tool_input}) => {result}")
        return tool_results

    def _final_choice(
        self,
        observation: str,
        choices: List[Dict[str, str]],
        tool_results: Optional[List[str]] = None,
    ) -> Tuple[LLMResponse, Dict[str, Any]]:
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

    def _remember_tool_step(
        self,
        observation: str,
        choices: List[Dict[str, str]],
        response: LLMResponse,
    ) -> None:
        selected_choice = ""
        if 1 <= response.action <= len(choices):
            selected_choice = choices[response.action - 1].get("text", "")

        clipped_observation = " ".join((observation or "").strip().split())
        if len(clipped_observation) > 180:
            clipped_observation = clipped_observation[:180] + "..."

        self._memory_entries.append(
            {
                "step": len(self._memory_entries) + 1,
                "observation": clipped_observation,
                "choices": [choice.get("text", "") for choice in choices],
                "selected_choice": selected_choice,
            }
        )
        if len(self._memory_entries) > 25:
            self._memory_entries = self._memory_entries[-25:]

    def _get_action_impl(self, state: str, choices: List[Dict[str, str]]) -> int:
        try:
            state_signature = self._state_signature(state, choices)
            self._ensure_llm()

            selection_prompt = self._build_tool_prompt(
                state,
                choices,
                prompt_kind="select",
            )
            selection_response = self.llm.get_completion(selection_prompt)
            selection_usage = self.llm.get_last_usage()
            tool_calls = self._extract_tool_calls(selection_response)
            parsed_response = parse_llm_response(
                selection_response,
                len(choices),
                self.debug,
                self.logger,
            )

            total_usage = self._normalize_usage(selection_usage)
            if tool_calls:
                tool_results = self._execute_tool_calls(tool_calls)
                parsed_response, final_usage = self._final_choice(
                    state,
                    choices,
                    tool_results=tool_results,
                )
                total_usage = self._normalize_usage(self._merge_usage(total_usage, final_usage))
            elif parsed_response.is_default:
                parsed_response, final_usage = self._final_choice(state, choices, tool_results=[])
                total_usage = self._normalize_usage(self._merge_usage(total_usage, final_usage))

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

            parsed_response.prompt_tokens = total_usage["prompt_tokens"]
            parsed_response.completion_tokens = total_usage["completion_tokens"]
            parsed_response.total_tokens = total_usage["total_tokens"]
            parsed_response.estimated_cost_usd = total_usage["estimated_cost_usd"]

            self.history.append(parsed_response)
            self._last_response = parsed_response
            self._remember_decision(state, choices, state_signature, parsed_response)
            self._remember_tool_step(state, choices, parsed_response)
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
        self._memory_entries = []

    def on_game_start(self) -> None:
        super().on_game_start()
        self._memory_entries = []
