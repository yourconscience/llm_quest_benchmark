"""State-based progress manifests and the runtime progress tracker.

Progress is a diagnostic that is deliberately separate from the authoritative
terminal outcome. Without a curated manifest a run reports terminal-only
progress rather than guessing story advancement.
"""

from __future__ import annotations

import functools
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from llm_quest_benchmark.schemas.records import ProgressState, QuestSnapshot, canonical_json

MANIFEST_VERSION = 1
_PREDICATE_KEYS = {
    "location_id",
    "game_state",
    "done",
    "params_contains",
    "observation_contains",
    "params_pattern",
}


@dataclass(frozen=True)
class Milestone:
    """One state predicate and the progress percentage it awards."""

    id: str
    percent: float
    match: dict[str, Any]
    description: str = ""

    @staticmethod
    @functools.cache
    def _compiled_pattern(pattern: str):
        return re.compile(pattern)

    def matches(self, snapshot: QuestSnapshot) -> bool:
        """All declared predicates must hold for the milestone to be reached."""
        params_text = "\n".join(snapshot.params_state)

        location_ids = self.match.get("location_id")
        if location_ids is not None and str(snapshot.location_id) not in location_ids:
            return False

        game_states = self.match.get("game_state")
        if game_states is not None and snapshot.game_state not in game_states:
            return False

        done = self.match.get("done")
        if done is not None and bool(snapshot.done) is not bool(done):
            return False

        for needle in self.match.get("params_contains") or []:
            if needle not in params_text:
                return False

        for needle in self.match.get("observation_contains") or []:
            if needle not in (snapshot.observation or ""):
                return False

        pattern_rule = self.match.get("params_pattern")
        if pattern_rule is not None:
            regex = Milestone._compiled_pattern(pattern_rule["pattern"])
            hits = sum(1 for line in snapshot.params_state if regex.search(line))
            if hits < int(pattern_rule.get("min_count", 1)):
                return False

        return True


@dataclass
class ProgressManifest:
    """Validated set of quest milestones loaded from YAML."""

    quest: str
    milestones: list[Milestone]
    source: str = ""
    version: int = MANIFEST_VERSION
    _hash_cache: str | None = field(default=None, init=False, repr=False, compare=False)

    @property
    def maximum(self) -> float:
        """Progress scale ceiling; terminal success always reports 100."""
        return 100.0

    @property
    def hash(self) -> str:
        """Digest of the milestone definitions that award progress.

        Recorded with every progress state so a run scored under a since-edited
        manifest is detectable instead of silently comparable.
        """
        if self._hash_cache is None:
            payload = [{"id": m.id, "percent": m.percent, "match": m.match} for m in self.milestones]
            self._hash_cache = hashlib.sha256(
                canonical_json({"quest": self.quest, "milestones": payload}).encode("utf-8")
            ).hexdigest()[:16]
        return self._hash_cache

    @classmethod
    def from_file(cls, path: str | Path) -> ProgressManifest:
        manifest_path = Path(path)
        if not manifest_path.exists():
            raise FileNotFoundError(f"Progress manifest not found: {manifest_path}")
        with open(manifest_path, encoding="utf-8") as f:
            payload = yaml.safe_load(f)
        return cls.from_dict(payload, source=str(manifest_path))

    @classmethod
    def from_dict(cls, payload: Any, source: str = "") -> ProgressManifest:
        if not isinstance(payload, dict):
            raise ValueError(f"Progress manifest must be a mapping: {source or '<inline>'}")

        version = payload.get("version", MANIFEST_VERSION)
        if version != MANIFEST_VERSION:
            raise ValueError(f"Unsupported progress manifest version {version!r} in {source or '<inline>'}")

        quest = str(payload.get("quest") or "").strip()
        if not quest:
            raise ValueError(f"Progress manifest is missing 'quest': {source or '<inline>'}")

        raw_milestones = payload.get("milestones")
        if not isinstance(raw_milestones, list) or not raw_milestones:
            raise ValueError(f"Progress manifest needs a non-empty 'milestones' list: {source or '<inline>'}")

        milestones: list[Milestone] = []
        seen_ids: set[str] = set()
        previous_percent = -1.0
        for entry in raw_milestones:
            if not isinstance(entry, dict):
                raise ValueError(f"Milestone entries must be mappings: {source or '<inline>'}")
            milestone_id = str(entry.get("id") or "").strip()
            if not milestone_id:
                raise ValueError(f"Milestone is missing 'id': {source or '<inline>'}")
            if milestone_id in seen_ids:
                raise ValueError(f"Duplicate milestone id '{milestone_id}' in {source or '<inline>'}")
            seen_ids.add(milestone_id)

            if "percent" not in entry:
                raise ValueError(f"Milestone '{milestone_id}' is missing 'percent'")
            percent = float(entry["percent"])
            if not (0.0 <= percent <= 100.0):
                raise ValueError(f"Milestone '{milestone_id}' percent must be within 0..100, got {percent}")
            if percent < previous_percent:
                raise ValueError(f"Milestone '{milestone_id}' percent decreases; list milestones in ascending order")
            previous_percent = percent

            match = entry.get("match")
            if not isinstance(match, dict) or not match:
                raise ValueError(f"Milestone '{milestone_id}' needs a non-empty 'match' mapping")
            unknown = set(match) - _PREDICATE_KEYS
            if unknown:
                raise ValueError(
                    f"Milestone '{milestone_id}' has unknown predicates: {sorted(unknown)}. "
                    f"Supported: {sorted(_PREDICATE_KEYS)}"
                )
            _validate_predicates(milestone_id, match)

            milestones.append(
                Milestone(
                    id=milestone_id,
                    percent=percent,
                    match=match,
                    description=str(entry.get("description") or ""),
                )
            )

        return cls(quest=quest, milestones=milestones, source=source, version=MANIFEST_VERSION)


def _validate_predicates(milestone_id: str, match: dict[str, Any]) -> None:
    for key in ("location_id", "game_state", "params_contains", "observation_contains"):
        value = match.get(key)
        if value is None:
            continue
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise ValueError(f"Milestone '{milestone_id}' predicate '{key}' must be a list of strings")

    if "done" in match and not isinstance(match["done"], bool):
        raise ValueError(f"Milestone '{milestone_id}' predicate 'done' must be a boolean")

    pattern_rule = match.get("params_pattern")
    if pattern_rule is not None:
        if not isinstance(pattern_rule, dict) or "pattern" not in pattern_rule:
            raise ValueError(f"Milestone '{milestone_id}' predicate 'params_pattern' needs a 'pattern' key")
        try:
            re.compile(str(pattern_rule["pattern"]))
        except re.error as exc:
            raise ValueError(f"Milestone '{milestone_id}' has an invalid params_pattern regex: {exc}") from exc
        min_count = pattern_rule.get("min_count", 1)
        if not isinstance(min_count, int) or min_count < 1:
            raise ValueError(f"Milestone '{milestone_id}' params_pattern min_count must be a positive integer")


@dataclass
class ProgressTracker:
    """Monotonic progress accumulator over observed snapshots.

    Reached milestones only accumulate, so ``current`` never decreases even when
    the backtracking harness restores an earlier checkpoint.
    """

    manifest: ProgressManifest | None = None
    _reached: list[str] = field(default_factory=list, init=False)
    _current: float = field(default=0.0, init=False)
    _stalled: int = field(default=0, init=False)

    @property
    def manifest_id(self) -> str | None:
        return self.manifest.source if self.manifest else None

    @property
    def manifest_hash(self) -> str | None:
        return self.manifest.hash if self.manifest else None

    @property
    def maximum(self) -> float:
        return self.manifest.maximum if self.manifest else 100.0

    def state(self, newly_reached: list[str] | None = None) -> ProgressState:
        return ProgressState(
            current=self._current,
            maximum=self.maximum,
            # Without a manifest the run is unscored: only terminal success moves
            # the number, so 0.0 means "not scored", not "no advancement".
            scored=self.manifest is not None,
            reached=list(self._reached),
            newly_reached=list(newly_reached or []),
            stalled_transitions=self._stalled,
            manifest=self.manifest_id,
            manifest_hash=self.manifest_hash,
        )

    def observe(self, snapshot: QuestSnapshot) -> ProgressState:
        """Fold one snapshot into progress and return the resulting state."""
        newly_reached: list[str] = []
        if self.manifest:
            for milestone in self.manifest.milestones:
                if milestone.id in self._reached:
                    continue
                if milestone.matches(snapshot):
                    self._reached.append(milestone.id)
                    newly_reached.append(milestone.id)
                    self._current = max(self._current, milestone.percent)

        # Terminal success is always full progress, with or without a manifest.
        if snapshot.game_state == "win":
            self._current = self.maximum

        if newly_reached:
            self._stalled = 0
        else:
            self._stalled += 1

        return self.state(newly_reached)

    def seed(self, snapshot: QuestSnapshot) -> ProgressState:
        """Fold the starting snapshot in without counting it as a stalled step."""
        state = self.observe(snapshot)
        self._stalled = 0
        return self.state(state.newly_reached)

    def restore_from(self, state: ProgressState) -> None:
        """Seed the tracker from a persisted state when resuming a run."""
        self._reached = list(state.reached)
        self._current = float(state.current)
        self._stalled = int(state.stalled_transitions)


def load_progress_manifest(path: str | None) -> ProgressManifest | None:
    """Load an optional manifest path from configuration or a resume record."""
    if not path:
        return None
    return ProgressManifest.from_file(path)
