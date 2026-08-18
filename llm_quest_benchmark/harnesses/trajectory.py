"""Append-only, full-fidelity, in-memory quest trajectory with bounded retrieval.

This is an online retrieval substrate for the ``programmatic_memory`` harness only.
``QuestLogger``/``run_summary.json`` remain the canonical persisted trajectory; this
component intentionally stores nothing to disk and is scoped to a single episode.
"""

import re
from dataclasses import dataclass

MAX_READ_COUNT = 6
MAX_SEARCH_RESULTS = 5
MAX_OUTPUT_CHARS = 8000

_SEARCH_TOKEN_PATTERN = re.compile(r"[a-zA-ZЀ-ӿ0-9_]+")
_INTEGER_STRING_PATTERN = re.compile(r"[+-]?\d+")
_ENTRY_TRUNCATION_MARKER = "... [entry truncated, exceeds character budget]"


@dataclass(frozen=True)
class TrajectoryStep:
    """One immutable, full-fidelity executed quest step."""

    step: int
    observation: str
    choices: tuple[str, ...]
    selected_action: int
    selected_choice: str


def _coerce_positive_int(value) -> int | None:
    """Strict integer coercion: an `int`, or a `str` containing only an integer,
    is valid; anything else (`None`, `bool`, any `float` including a whole
    number like `2.0`, or a decimal string like `"1.5"`) returns None. Sign is
    not checked here -- a syntactically valid but non-positive value (e.g. -1)
    is still returned, so callers can report a "must be positive" error
    distinct from a "not an integer" error. `int(1.5)` truncating to 1 would
    silently answer a different question than the one the caller asked, so
    non-integral values are rejected rather than coerced.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if _INTEGER_STRING_PATTERN.fullmatch(stripped):
            return int(stripped)
        return None
    return None


class Trajectory:
    """Append-only, full-fidelity step history for one quest episode.

    Invariants: append once per executed step, preserve insertion order, never
    mutate earlier entries, and reset entirely between episodes. Read/search bound
    their OUTPUT by entry count and character budget; they never truncate what is
    stored.
    """

    def __init__(self):
        self._steps: list[TrajectoryStep] = []

    def __len__(self) -> int:
        return len(self._steps)

    def reset(self) -> None:
        self._steps = []

    def append(
        self,
        observation: str,
        choices: list[str],
        selected_action: int,
        selected_choice: str,
    ) -> TrajectoryStep:
        """Append one executed step. Call exactly once per decision, after the
        final executed choice is known."""
        step = TrajectoryStep(
            step=len(self._steps) + 1,
            observation=(observation or "").strip(),
            choices=tuple(choices),
            selected_action=selected_action,
            selected_choice=selected_choice or "",
        )
        self._steps.append(step)
        return step

    def recent(self, window: int) -> list[TrajectoryStep]:
        """Return copies (immutable dataclasses) of the last `window` steps."""
        if window <= 0:
            return []
        return list(self._steps[-window:])

    def read(self, start_step, count) -> str:
        """Deterministic bounded consecutive-range read, 1-based and inclusive."""
        if not self._steps:
            return "error: no history recorded yet"

        start = _coerce_positive_int(start_step)
        if start is None or start < 1:
            return "error: start_step must be a positive integer"
        if start > len(self._steps):
            return f"error: start_step out of range (1-{len(self._steps)} recorded)"

        requested = _coerce_positive_int(count)
        if requested is None or requested < 1:
            return "error: count must be a positive integer"

        bounded_count = min(requested, MAX_READ_COUNT)
        end = min(start + bounded_count - 1, len(self._steps))
        entries = self._steps[start - 1 : end]
        return self._format_entries(entries)

    def search(self, query: str, limit) -> str:
        """Literal, case-insensitive token search; rank by match count, then recency."""
        if not self._steps:
            return "error: no history recorded yet"

        stripped = (query or "").strip()
        if not stripped:
            return "error: empty query"

        tokens = set(_SEARCH_TOKEN_PATTERN.findall(stripped.lower()))
        if not tokens:
            return "error: query has no searchable tokens"

        requested_limit = _coerce_positive_int(limit) if limit is not None else MAX_SEARCH_RESULTS
        if requested_limit is None or requested_limit < 1:
            return "error: limit must be a positive integer"
        bounded_limit = min(requested_limit, MAX_SEARCH_RESULTS)

        scored = []
        for entry in self._steps:
            haystack = " ".join([entry.observation, " ".join(entry.choices), entry.selected_choice]).lower()
            score = sum(1 for token in tokens if token in haystack)
            if score > 0:
                scored.append((score, entry))

        if not scored:
            return f"no matches for query in {len(self._steps)} recorded steps"

        scored.sort(key=lambda item: (item[0], item[1].step), reverse=True)
        entries = [entry for _, entry in scored[:bounded_limit]]
        return self._format_entries(entries)

    @staticmethod
    def _format_entries(entries: list[TrajectoryStep]) -> str:
        """Join formatted entries into a result hard-bounded by MAX_OUTPUT_CHARS.

        Only the FORMATTED output is ever truncated; the underlying
        `TrajectoryStep` objects (stored history) are immutable and untouched.

        Room for the trailing omission marker ("N of M steps shown...") is
        reserved up front, before any entry is admitted, by capping entry
        admission at `entry_budget = MAX_OUTPUT_CHARS - omission_reserve`
        rather than the raw `MAX_OUTPUT_CHARS`. This is what guarantees an
        already-admitted whole entry is never retroactively sliced to make
        room for that marker: every admitted entry already fits with the
        marker's worst-case length accounted for, so appending it afterward
        never requires touching entry text again.

        Whole entries are still preferred over slicing: a later entry that
        would not fit is dropped whole, never sliced. Only if even the first
        entry alone exceeds `entry_budget` is its formatted text truncated,
        with an explicit marker; if more entries remain beyond it, the
        omission marker is appended after that truncated entry too, so
        "clearly marked truncated first entry plus an omission indication"
        can never be indistinguishable from "N whole entries, none touched".
        The result is always `len(result) <= MAX_OUTPUT_CHARS`.
        """
        if not entries:
            return ""

        total_entries = len(entries)
        # Worst-case marker length: using `total_entries` for both digit
        # placeholders is always >= the real marker's length, since `included`
        # can never exceed `total_entries`. No marker is possible at all when
        # there is only one entry to begin with.
        omission_reserve = (
            len(f"\n... [{total_entries} of {total_entries} steps shown; remaining omitted, character budget]")
            if total_entries > 1
            else 0
        )
        entry_budget = max(MAX_OUTPUT_CHARS - omission_reserve, 0)

        lines = []
        total_len = 0
        for entry in entries:
            choices_text = "; ".join(entry.choices) if entry.choices else "(none)"
            line = (
                f"Step {entry.step}: observation={entry.observation} | "
                f"choices={choices_text} | selected={entry.selected_action}: {entry.selected_choice}"
            )
            projected_len = total_len + len(line) + (1 if lines else 0)
            if lines and projected_len > entry_budget:
                break
            if not lines and len(line) > entry_budget:
                budget = max(entry_budget - len(_ENTRY_TRUNCATION_MARKER), 0)
                line = line[:budget] + _ENTRY_TRUNCATION_MARKER
                lines.append(line)
                total_len = len(line)
                break
            lines.append(line)
            total_len = projected_len

        text = "\n".join(lines)
        included = len(lines)
        if included < total_entries:
            text += f"\n... [{included} of {total_entries} steps shown; remaining omitted, character budget]"

        return text[:MAX_OUTPUT_CHARS]
