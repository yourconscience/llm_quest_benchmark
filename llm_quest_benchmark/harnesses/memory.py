"""Memory modules for harness-based quest players."""

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class MemoryModule(ABC):
    @abstractmethod
    def get_context(self, step: int) -> str:
        pass

    @abstractmethod
    def update(self, step_data: dict) -> None:
        pass

    @abstractmethod
    def reset(self) -> None:
        pass

    @property
    def quest_briefing(self) -> str | None:
        return None

    @property
    def transcript(self) -> list[dict[str, Any]]:
        return []

    @transcript.setter
    def transcript(self, value: list[dict[str, Any]]) -> None:
        raise TypeError(f"{self.__class__.__name__} does not support transcript assignment")

    @property
    def steps_since_compaction(self) -> int:
        return 0

    @steps_since_compaction.setter
    def steps_since_compaction(self, value: int) -> None:
        raise TypeError(f"{self.__class__.__name__} does not support compaction counters")

    def set_quest_briefing(self, briefing: str) -> None:
        clean = (briefing or "").strip()
        if hasattr(self, "_quest_briefing"):
            self._quest_briefing = clean or None

    def _briefing_block(self, current_state: str) -> str | None:
        briefing = self.quest_briefing
        if not briefing:
            return None
        if current_state.strip() == briefing:
            return None
        if len(briefing) > 800:
            briefing = briefing[:800] + "..."
        return f"Quest briefing (your mission):\n{briefing}"


class DefaultMemory(MemoryModule):
    """Recent N observations window without compaction."""

    def __init__(self, context_window: int = 3, context_chars: int = 220, decision_window: int = 5):
        self.context_window = context_window
        self.context_chars = context_chars
        self.decision_window = decision_window
        self._quest_briefing: str | None = None
        self._observations: list[str] = []
        self._decisions: list[dict[str, Any]] = []

    @property
    def quest_briefing(self) -> str | None:
        return self._quest_briefing

    def get_context(self, step: int) -> str:
        blocks: list[str] = []
        current = self._observations[-1] if self._observations else ""

        briefing = self._briefing_block(current)
        if briefing:
            blocks.append(briefing)

        if len(self._observations) > 1:
            previous = self._observations[:-1][-self.context_window :]
            if previous:
                snippets = []
                for idx, text in enumerate(previous, start=1):
                    clipped = text if len(text) <= self.context_chars else text[: self.context_chars] + "..."
                    snippets.append(f"[Previous {idx}] {clipped}")
                blocks.append("Recent context from previous steps:\n" + "\n\n".join(snippets))

        if self._decisions:
            recent_memos = []
            for item in self._decisions[-self.decision_window :]:
                memo = (item.get("memo") or "").strip()
                if not memo:
                    continue
                if recent_memos and recent_memos[-1] == memo:
                    continue
                recent_memos.append(memo)
            if recent_memos:
                lines = [f"[Memo {idx}] {memo}" for idx, memo in enumerate(recent_memos, start=1)]
                blocks.append("State memo (recent):\n" + "\n".join(lines))

            decision_lines = []
            for idx, item in enumerate(self._decisions[-self.decision_window :], start=1):
                choice = item.get("choice") or item.get("choice_text", "")
                parse_mode = item.get("parse_mode", "unknown")
                memo_val = item.get("memo")
                memo_suffix = f" | memo: {memo_val}" if memo_val else ""
                decision_lines.append(
                    f"[Decision {idx}] action {item.get('action')}: {choice} (parse={parse_mode}){memo_suffix}"
                )
            blocks.append("Recent selected actions:\n" + "\n".join(decision_lines))

        return "\n\n".join(blocks)

    def update(self, step_data: dict) -> None:
        observation = (step_data.get("observation") or step_data.get("state") or "").strip()
        if observation:
            if self._quest_briefing is None:
                self._quest_briefing = observation
            self._observations.append(observation)
            if len(self._observations) > 20:
                self._observations = self._observations[-20:]

        if any(key in step_data for key in ("action", "choice", "choice_text", "memo")):
            memo = (step_data.get("memo") or "").strip()[:350] or None
            self._decisions.append(
                {
                    "action": step_data.get("action"),
                    "choice": step_data.get("choice") or step_data.get("choice_text", ""),
                    "parse_mode": step_data.get("parse_mode", "unknown"),
                    "memo": memo,
                }
            )
            if len(self._decisions) > 40:
                self._decisions = self._decisions[-40:]

    def reset(self) -> None:
        self._quest_briefing = None
        self._observations = []
        self._decisions = []


class FullTranscriptMemory(MemoryModule):
    """Unbounded full transcript in context."""

    def __init__(self):
        self._quest_briefing: str | None = None
        self._transcript: list[dict[str, Any]] = []

    @property
    def quest_briefing(self) -> str | None:
        return self._quest_briefing

    @property
    def transcript(self) -> list[dict[str, Any]]:
        return self._transcript

    @transcript.setter
    def transcript(self, value: list[dict[str, Any]]) -> None:
        self._transcript = value

    def get_context(self, step: int) -> str:
        blocks: list[str] = []
        current_state = self._transcript[-1].get("observation", "") if self._transcript else ""
        briefing = self._briefing_block(current_state)
        if briefing:
            blocks.append(briefing)

        if self._transcript:
            lines = []
            for entry in self._transcript:
                step_value = entry.get("step", "?")
                obs = entry.get("observation", "")
                if len(obs) > 400:
                    obs = obs[:400] + "..."
                chosen = entry.get("choice_text") or entry.get("choice", "")
                reasoning = entry.get("reasoning", "")
                line = f"Step {step_value}: {obs}"
                if chosen:
                    line += f"\n  You chose: {chosen}"
                if reasoning:
                    line += f"\n  Reasoning: {reasoning[:800]}"
                state_notes = entry.get("memo", "")
                if state_notes:
                    line += f"\n  State: {state_notes[:350]}"
                lines.append(line)
            blocks.append("=== QUEST TRANSCRIPT ===\n" + "\n\n".join(lines))

        return "\n\n".join(blocks)

    def update(self, step_data: dict) -> None:
        observation = (step_data.get("observation") or step_data.get("state") or "").strip()
        if observation and self._quest_briefing is None:
            self._quest_briefing = observation
        entry = dict(step_data)
        entry["observation"] = observation
        entry["step"] = entry.get("step") or len(self._transcript) + 1
        self._transcript.append(entry)

    def reset(self) -> None:
        self._quest_briefing = None
        self._transcript = []


class CompactionMemory(MemoryModule):
    """Periodic LLM summarization plus 20-word memo field."""

    def __init__(self, compaction_interval: int = 50, llm_client=None):
        self.compaction_interval = compaction_interval
        self.llm_client = llm_client
        self._quest_briefing: str | None = None
        self._transcript: list[dict[str, Any]] = []
        self._compaction_summary: str | None = None
        self._steps_since_compaction = 0

    @property
    def quest_briefing(self) -> str | None:
        return self._quest_briefing

    @property
    def transcript(self) -> list[dict[str, Any]]:
        return self._transcript

    @transcript.setter
    def transcript(self, value: list[dict[str, Any]]) -> None:
        self._transcript = value

    @property
    def steps_since_compaction(self) -> int:
        return self._steps_since_compaction

    @steps_since_compaction.setter
    def steps_since_compaction(self, value: int) -> None:
        self._steps_since_compaction = value

    def get_context(self, step: int) -> str:
        blocks: list[str] = []
        current_state = self._transcript[-1].get("observation", "") if self._transcript else ""
        briefing = self._briefing_block(current_state)
        if briefing:
            blocks.append(briefing)

        if self._compaction_summary:
            compacted_at = max(0, step - self._steps_since_compaction)
            blocks.append(f"=== QUEST MEMORY (compacted at step {compacted_at}) ===\n{self._compaction_summary}")

        recent = self._transcript[-self._steps_since_compaction :] if self._steps_since_compaction > 0 else []
        if recent:
            lines = []
            for entry in recent:
                step_value = entry.get("step", "?")
                obs = entry.get("observation", "")
                if len(obs) > 400:
                    obs = obs[:400] + "..."
                chosen = entry.get("choice_text") or entry.get("choice", "")
                line = f"Step {step_value}: {obs}"
                if chosen:
                    line += f"\n  You chose: {chosen}"
                state_notes = entry.get("memo", "")
                if state_notes:
                    line += f"\n  State: {state_notes[:350]}"
                lines.append(line)
            blocks.append("=== RECENT STEPS ===\n" + "\n\n".join(lines))

        return "\n\n".join(blocks)

    def update(self, step_data: dict) -> None:
        observation = (step_data.get("observation") or step_data.get("state") or "").strip()
        if observation and self._quest_briefing is None:
            self._quest_briefing = observation
        entry = dict(step_data)
        entry["observation"] = observation[:400]
        entry["step"] = entry.get("step") or len(self._transcript) + 1
        if entry.get("memo"):
            entry["memo"] = self._twenty_word_memo(str(entry["memo"]))
        self._transcript.append(entry)
        self._steps_since_compaction += 1
        self._maybe_compact()

    def reset(self) -> None:
        self._quest_briefing = None
        self._transcript = []
        self._compaction_summary = None
        self._steps_since_compaction = 0

    def _maybe_compact(self) -> None:
        if self._steps_since_compaction < self.compaction_interval:
            return
        if self.llm_client is None:
            logger.debug("Skipping compaction because no LLM client is attached")
            return
        transcript_text = self._format_transcript_for_compaction()
        if not transcript_text:
            self._steps_since_compaction = 0
            return

        prompt_parts = ["You are summarizing a quest player's progress through a text quest."]
        if self._quest_briefing:
            prompt_parts.append(f"\nQUEST BRIEFING (the original mission):\n{self._quest_briefing}")
        if self._compaction_summary:
            prompt_parts.append(f"\nPREVIOUS SUMMARY:\n{self._compaction_summary}")
        prompt_parts.append(f"\nTRANSCRIPT OF LAST {self._steps_since_compaction} STEPS:\n{transcript_text}")
        prompt_parts.append(
            "\nSummarize the agent's progress. Include:\n"
            "- Current objective (what the player should do next)\n"
            "- Progress so far (what has been accomplished)\n"
            "- Key facts (NPCs, items, locations, deadlines discovered)\n"
            "- Failed approaches (actions/paths that didn't work)\n"
            "- Map knowledge (locations visited and connections)\n\n"
            "Write a concise summary in plain text, max 300 words."
        )

        try:
            summary = (self.llm_client.get_completion("\n".join(prompt_parts)) or "").strip()
        except Exception as exc:
            logger.debug("Skipping compaction because summarization failed: %s", exc)
            self._steps_since_compaction = 0
            return
        if summary:
            self._compaction_summary = summary
            self._transcript = []
        self._steps_since_compaction = 0

    def _format_transcript_for_compaction(self) -> str:
        recent = (
            self._transcript[-self._steps_since_compaction :]
            if self._steps_since_compaction > 0
            else self._transcript[-self.compaction_interval :]
        )
        lines = []
        for entry in recent:
            step = entry.get("step", "?")
            obs = entry.get("observation", "")
            if len(obs) > 400:
                obs = obs[:400] + "..."
            chosen = entry.get("choice_text") or entry.get("choice", "")
            reasoning = entry.get("reasoning", "")
            state_notes = entry.get("memo", "")
            line = f"Step {step}: {obs}"
            if chosen:
                line += f"\n  Chose: {chosen}"
            if state_notes:
                line += f"\n  State: {state_notes[:350]}"
            if reasoning:
                line += f"\n  Reasoning: {reasoning[:800]}"
            lines.append(line)
        return "\n\n".join(lines)

    @staticmethod
    def _twenty_word_memo(memo: str) -> str:
        return " ".join(memo.split()[:20])
