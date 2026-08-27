"""Experimental backtracking harness.

This is the only harness whose specification declares the choose-or-restore
loop. Restores are budgeted by ``restore_limit`` and remain visible as
transitions in the persisted record.
"""

from typing import Any

from llm_quest_benchmark.constants import DEFAULT_MODEL, DEFAULT_TEMPERATURE, SYSTEM_ROLE_TEMPLATE
from llm_quest_benchmark.harnesses.base import BaseHarness, _parse_json_response
from llm_quest_benchmark.harnesses.memory import CompactionMemory
from llm_quest_benchmark.players.base import DecisionContext
from llm_quest_benchmark.schemas.records import QuestAction, QuestSnapshot
from llm_quest_benchmark.schemas.response import LLMResponse

DEFAULT_RESTORE_LIMIT = 3
CHECKPOINT_SUMMARY_CHARS = 140


def parse_restore_request(response: str, max_checkpoint: int) -> int | None:
    """Extract a valid restore checkpoint index from a model response.

    Returns None when the model did not ask for a restore or asked for an index
    outside the active branch.
    """
    if max_checkpoint < 1:
        return None

    payload, _ = _parse_json_response(response)
    if not isinstance(payload, dict):
        return None

    requested = payload.get("checkpoint")
    if str(payload.get("action") or "").strip().lower() != "restore":
        # A bare {"restore": N} is also accepted.
        requested = payload.get("restore", None) if "restore" in payload else None
        if requested is None:
            return None

    try:
        index = int(requested)
    except (TypeError, ValueError):
        return None
    if 1 <= index <= max_checkpoint:
        return index
    return None


def summarize_checkpoint(index: int, snapshot: QuestSnapshot) -> str:
    """One-line checkpoint description shown to the model."""
    text = " ".join((snapshot.observation or "").split())
    if len(text) > CHECKPOINT_SUMMARY_CHARS:
        text = text[:CHECKPOINT_SUMMARY_CHARS] + "..."
    params = "; ".join(snapshot.params_state[:4])
    suffix = f" | {params}" if params else ""
    return f"[{index}] location {snapshot.location_id}: {text}{suffix}"


class BacktrackingHarness(BaseHarness):
    """Compacted-memory harness that may choose an option or restore a checkpoint."""

    harness_name = "backtracking"
    supports_restore = True

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        system_template: str = SYSTEM_ROLE_TEMPLATE,
        action_template: str = "backtracking.jinja",
        temperature: float = DEFAULT_TEMPERATURE,
        skip_single: bool = False,
        debug: bool = False,
        compaction_interval: int = 50,
        restore_limit: int | None = None,
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
            memory_module=memory_module or CompactionMemory(compaction_interval=compaction_interval),
        )
        self.restore_limit = int(restore_limit) if restore_limit is not None else DEFAULT_RESTORE_LIMIT
        self._compaction_interval = compaction_interval
        self._context = DecisionContext()
        self._pending_restore: int | None = None

    def reset(self) -> None:
        super().reset()
        self._context = DecisionContext()
        self._pending_restore = None

    def get_quest_action(
        self,
        observation: str,
        choices: list[dict[str, str]],
        context: DecisionContext,
    ) -> QuestAction:
        """Choose a current option or restore a recorded checkpoint."""
        self._context = context
        self._pending_restore = None
        action_index = self.get_action(observation, choices)
        if self._pending_restore is not None:
            checkpoint = self._pending_restore
            self._pending_restore = None
            return QuestAction.restore(checkpoint)
        return QuestAction(kind="choose", choice_index=action_index)

    def _restorable_checkpoints(self) -> list[str]:
        # The last checkpoint is the current state, so it is never restorable.
        return [
            summarize_checkpoint(index, snapshot)
            for index, snapshot in enumerate(self._context.checkpoints[:-1], start=1)
        ]

    def _build_prompt(self, observation: str, choices: list[dict[str, str]]) -> str:
        template = self.prompt_renderer.get_template(self.action_template)
        return template.render(
            observation=observation,
            choices=[{"text": choice.get("text", "")} for choice in choices],
            checkpoints=self._restorable_checkpoints(),
            restore_allowed=self._context.restore_allowed,
            restores_remaining=self._context.restores_remaining,
        ).strip()

    def _get_action_impl(self, observation: str, choices: list[dict[str, str]]) -> int:
        try:
            state_signature = self._state_signature(observation, choices)
            contextual_state = self._build_contextual_state(observation)
            prompt = self._build_prompt(contextual_state, choices)

            raw_response = self._call_llm(prompt)
            usage: dict[str, Any] = self.llm.get_last_usage()

            max_checkpoint = max(0, len(self._context.checkpoints) - 1)
            checkpoint = None
            if self._context.restore_allowed:
                checkpoint = parse_restore_request(raw_response, max_checkpoint)

            parsed_response = self._parse_llm_response(raw_response, len(choices))
            if checkpoint is None and parsed_response.is_default:
                retry_raw = self._call_llm(self._format_retry_prompt(observation, choices))
                usage = self._merge_usage(usage, self.llm.get_last_usage())
                retry_parsed = self._parse_llm_response(retry_raw, len(choices))
                if not retry_parsed.is_default:
                    retry_parsed.parse_mode = f"retry_{retry_parsed.parse_mode or 'parsed'}"
                    parsed_response = retry_parsed

            if checkpoint is None:
                action_before_policy = parsed_response.action
                parsed_response.action = self._apply_safety_filter(choices, parsed_response.action)
                if parsed_response.action != action_before_policy and not parsed_response.reasoning:
                    parsed_response.reasoning = "policy_safety_override"
            else:
                self._pending_restore = checkpoint
                parsed_response.parse_mode = "restore"
                parsed_response.reasoning = parsed_response.reasoning or f"restore_checkpoint_{checkpoint}"

            if parsed_response.action < 1 or parsed_response.action > len(choices):
                parsed_response.action = 1

            usage_payload = self._normalize_usage(usage)
            parsed_response.prompt_tokens = usage_payload["prompt_tokens"]
            parsed_response.completion_tokens = usage_payload["completion_tokens"]
            parsed_response.total_tokens = usage_payload["total_tokens"]
            parsed_response.estimated_cost_usd = usage_payload["estimated_cost_usd"]

            self.history.append(parsed_response)
            self._last_response = parsed_response
            self._remember_decision(observation, choices, state_signature, parsed_response)
            return parsed_response.action
        except Exception as exc:
            self.logger.error("Backtracking harness error during LLM call: %s", exc)
            default_response = LLMResponse(
                action=1,
                is_default=True,
                parse_mode="error_default",
                reasoning=f"backtracking_error: {exc}",
            )
            self.history.append(default_response)
            self._last_response = default_response
            return 1
