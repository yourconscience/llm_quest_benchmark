"""Memory modules for harness-based quest agents."""

from abc import ABC, abstractmethod
from typing import Any


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

    def set_quest_briefing(self, briefing: str) -> None:
        pass


class DefaultMemory(MemoryModule):
    """Recent N observations window (no compaction)."""

    def __init__(self, context_window: int = 3, context_chars: int = 220, decision_window: int = 5):
        self.context_window = context_window
        self.context_chars = context_chars
        self.decision_window = decision_window
        self._quest_briefing: str | None = None
        self._observations: list[str] = []
        self._decisions: list[dict[str, Any]] = []

    def set_quest_briefing(self, briefing: str) -> None:
        clean = (briefing or "").strip()
        self._quest_briefing = clean or None

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

    def _briefing_block(self, current_state: str) -> str | None:
        if not self._quest_briefing:
            return None
        if current_state.strip() == self._quest_briefing:
            return None
        briefing = self._quest_briefing
        if len(briefing) > 800:
            briefing = briefing[:800] + "..."
        return f"Quest briefing (your mission):\n{briefing}"


class FullTranscriptMemory(MemoryModule):
    """Unbounded full transcript in context."""

    def __init__(self):
        self._quest_briefing: str | None = None
        self._transcript: list[dict[str, Any]] = []

    def set_quest_briefing(self, briefing: str) -> None:
        clean = (briefing or "").strip()
        self._quest_briefing = clean or None

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

    def _briefing_block(self, current_state: str) -> str | None:
        if not self._quest_briefing:
            return None
        if current_state.strip() == self._quest_briefing:
            return None
        briefing = self._quest_briefing
        if len(briefing) > 800:
            briefing = briefing[:800] + "..."
        return f"Quest briefing (your mission):\n{briefing}"


class CompactionMemory(MemoryModule):
    """Periodic LLM summarization + 20-word memo field."""

    def __init__(self, compaction_interval: int = 50, llm_client=None):
        self.compaction_interval = compaction_interval
        self.llm_client = llm_client
        self._quest_briefing: str | None = None
        self._transcript: list[dict[str, Any]] = []
        self._compaction_summary: str | None = None
        self._steps_since_compaction = 0

    def set_quest_briefing(self, briefing: str) -> None:
        clean = (briefing or "").strip()
        self._quest_briefing = clean or None

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
            # No LLM client available for compaction; skip silently
            return
        transcript_text = self._format_transcript_for_compaction()
        if not transcript_text:
            return

        prompt_parts = ["You are summarizing an agent's progress through a text quest."]
        if self._quest_briefing:
            prompt_parts.append(f"\nQUEST BRIEFING (the original mission):\n{self._quest_briefing}")
        if self._compaction_summary:
            prompt_parts.append(f"\nPREVIOUS SUMMARY:\n{self._compaction_summary}")
        prompt_parts.append(f"\nTRANSCRIPT OF LAST {self._steps_since_compaction} STEPS:\n{transcript_text}")
        prompt_parts.append(
            "\nSummarize the agent's progress. Include:\n"
            "- Current objective (what the agent should do next)\n"
            "- Progress so far (what has been accomplished)\n"
            "- Key facts (NPCs, items, locations, deadlines discovered)\n"
            "- Failed approaches (actions/paths that didn't work)\n"
            "- Map knowledge (locations visited and connections)\n\n"
            "Write a concise summary in plain text, max 300 words."
        )

        summary = (self.llm_client.get_completion("\n".join(prompt_parts)) or "").strip()
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

    def _briefing_block(self, current_state: str) -> str | None:
        if not self._quest_briefing:
            return None
        if current_state.strip() == self._quest_briefing:
            return None
        briefing = self._quest_briefing
        if len(briefing) > 800:
            briefing = briefing[:800] + "..."
        return f"Quest briefing (your mission):\n{briefing}"

    @staticmethod
    def _twenty_word_memo(memo: str) -> str:
        return " ".join(memo.split()[:20])
