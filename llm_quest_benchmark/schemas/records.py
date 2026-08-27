"""Canonical schema-v2 run record types.

These types are the only transition/run representation accepted at runtime.
Legacy shapes are read exclusively by ``llm_quest_benchmark.core.migration``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

from llm_quest_benchmark.schemas.response import LLMResponse

SCHEMA_VERSION = 2

# Provenance of a persisted transition.
PROVENANCE_RUNTIME = "runtime"
PROVENANCE_LEGACY_MAPPED = "legacy_mapped"

# Replay status of a persisted transition.
REPLAY_PENDING = "pending"
REPLAY_VERIFIED = "verified"
REPLAY_UNAVAILABLE = "unavailable"

ACTION_CHOOSE = "choose"
ACTION_RESTORE = "restore"
ACTION_KINDS = (ACTION_CHOOSE, ACTION_RESTORE)

# Marker for state that a legacy record cannot prove.
GAME_STATE_UNAVAILABLE = "unavailable"

# Nested domains every schema-v2 run record must carry.
RUN_RECORD_DOMAINS = (
    "run",
    "quest",
    "treatment",
    "lineage",
    "terminal",
    "usage",
    "progress",
    "transcript_diagnostics",
    "transitions",
)

MIGRATION_HINT = "run `llm-quest migrate-records --source PATH --output PATH` to convert legacy records."


def canonical_json(payload: Any) -> str:
    """Stable JSON encoding used for digests and signatures."""
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def _digest(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _require_mapping(value: Any, domain: str) -> dict[str, Any]:
    """Return a required record domain, rejecting anything that is not a mapping."""
    if not isinstance(value, dict):
        raise ValueError(
            f"Run record domain '{domain}' must be an object, got {type(value).__name__}; {MIGRATION_HINT}"
        )
    return value


@dataclass
class QuestAction:
    """One executed environment action.

    ``choose`` carries the one-based choice index, the engine jump id, and the
    exact ``performed_at_ms`` handed to ``performJump``. ``restore`` carries the
    one-based checkpoint index selected by the backtracking harness.
    """

    kind: str
    choice_index: int | None = None
    choice_id: str | None = None
    performed_at_ms: int | None = None
    checkpoint_index: int | None = None

    @classmethod
    def choose(cls, choice_index: int, choice_id: str, performed_at_ms: int) -> QuestAction:
        return cls(
            kind=ACTION_CHOOSE,
            choice_index=int(choice_index),
            choice_id=str(choice_id),
            performed_at_ms=int(performed_at_ms),
        )

    @classmethod
    def restore(cls, checkpoint_index: int) -> QuestAction:
        return cls(kind=ACTION_RESTORE, checkpoint_index=int(checkpoint_index))

    @property
    def is_choose(self) -> bool:
        return self.kind == ACTION_CHOOSE

    @property
    def is_restore(self) -> bool:
        return self.kind == ACTION_RESTORE

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> QuestAction:
        """Rebuild an action, rejecting any kind outside the canonical set."""
        if not isinstance(payload, dict):
            raise ValueError(f"Quest action must be an object, got {type(payload).__name__}")
        kind = str(payload.get("kind") or "")
        if kind not in ACTION_KINDS:
            raise ValueError(f"Unsupported quest action kind {kind!r}; expected one of {list(ACTION_KINDS)}")
        return cls(
            kind=kind,
            choice_index=payload.get("choice_index"),
            choice_id=payload.get("choice_id"),
            performed_at_ms=payload.get("performed_at_ms"),
            checkpoint_index=payload.get("checkpoint_index"),
        )


@dataclass
class QuestSnapshot:
    """Complete environment state at one point in a run."""

    location_id: str
    observation: str
    choices: list[dict[str, str]] = field(default_factory=list)
    params_state: list[str] = field(default_factory=list)
    reward: float = 0.0
    done: bool = False
    game_state: str = "running"
    saving: dict[str, Any] | None = None
    digest: str = ""
    # Fields a legacy record could not prove. Never part of the digest.
    unavailable_fields: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.digest:
            self.digest = self.compute_digest()

    @classmethod
    def unavailable(cls, missing: list[str] | None = None) -> QuestSnapshot:
        """Snapshot placeholder for state a legacy record cannot reconstruct."""
        return cls(
            location_id="",
            observation="",
            game_state=GAME_STATE_UNAVAILABLE,
            unavailable_fields=missing or ["location_id", "observation", "choices", "params_state", "saving"],
        )

    @property
    def is_unavailable(self) -> bool:
        return self.game_state == GAME_STATE_UNAVAILABLE

    def digest_payload(self) -> dict[str, Any]:
        """Canonical fields covered by the snapshot digest."""
        return {
            "location_id": str(self.location_id),
            "observation": self.observation,
            "choices": [{"id": str(c.get("id", "")), "text": c.get("text", "")} for c in self.choices],
            "params_state": list(self.params_state),
            "done": bool(self.done),
            "game_state": self.game_state,
            "saving": self.saving,
        }

    def compute_digest(self) -> str:
        return _digest(self.digest_payload())

    def agent_observation(self) -> str:
        """Observation text as presented to an agent (quest text plus params)."""
        base = (self.observation or "").strip()
        lines = [str(p).strip() for p in self.params_state if str(p).strip()]
        if not lines:
            return base
        params_block = "Status:\n" + "\n".join(lines)
        return f"{base}\n\n{params_block}" if base else params_block

    @property
    def is_resumable(self) -> bool:
        """A snapshot can seed a resumed run only with a full engine saving."""
        return isinstance(self.saving, dict) and bool(self.saving) and not self.is_unavailable

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> QuestSnapshot:
        choices_raw = payload.get("choices") or []
        choices = [
            {"id": str(c.get("id", "")), "text": str(c.get("text", ""))} for c in choices_raw if isinstance(c, dict)
        ]
        return cls(
            location_id=str(payload.get("location_id", "")),
            observation=str(payload.get("observation") or ""),
            choices=choices,
            params_state=[str(p) for p in (payload.get("params_state") or [])],
            reward=float(payload.get("reward") or 0.0),
            done=bool(payload.get("done", False)),
            game_state=str(payload.get("game_state") or "running"),
            saving=payload.get("saving") if isinstance(payload.get("saving"), dict) else None,
            digest=str(payload.get("digest") or ""),
            unavailable_fields=[str(f) for f in (payload.get("unavailable_fields") or [])],
        )


@dataclass
class ProgressState:
    """Monotonic milestone progress derived from a curated manifest.

    ``scored`` says whether a curated manifest was in effect. An unscored state
    is terminal-only progress: it never guesses story advancement, so a 0.0
    ``current`` means "no manifest", not "no progress made".

    ``current`` never decreases within a run, including after a restore.
    ``maximum`` is the highest percentage the active manifest can award, so
    ``current / maximum`` is a well-defined completion ratio. ``manifest_hash``
    pins the exact milestone definitions that produced these numbers, so
    progress recorded under a since-edited manifest is detectable.
    """

    current: float = 0.0
    maximum: float = 100.0
    scored: bool = False
    reached: list[str] = field(default_factory=list)
    newly_reached: list[str] = field(default_factory=list)
    stalled_transitions: int = 0
    manifest: str | None = None
    manifest_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> ProgressState:
        payload = payload or {}
        return cls(
            current=float(payload.get("current") or 0.0),
            maximum=float(payload.get("maximum") or 100.0),
            scored=bool(payload.get("scored", False)),
            reached=[str(m) for m in (payload.get("reached") or [])],
            newly_reached=[str(m) for m in (payload.get("newly_reached") or [])],
            stalled_transitions=int(payload.get("stalled_transitions") or 0),
            manifest=payload.get("manifest"),
            manifest_hash=payload.get("manifest_hash"),
        )


@dataclass
class QuestTransition:
    """One executed environment transition plus its agent-side provenance."""

    index: int
    before: QuestSnapshot
    action: QuestAction
    after: QuestSnapshot
    response: LLMResponse | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    progress: ProgressState = field(default_factory=ProgressState)
    provenance: str = PROVENANCE_RUNTIME
    replay_status: str = REPLAY_PENDING
    reasoning_mode: str | None = None

    @property
    def is_replayable(self) -> bool:
        """Whether this transition carries every deterministic replay input."""
        if self.replay_status == REPLAY_UNAVAILABLE:
            return False
        if not self.before.is_resumable or not self.after.is_resumable:
            return False
        if self.action.is_choose:
            return self.action.choice_id is not None and self.action.performed_at_ms is not None
        if self.action.is_restore:
            return self.action.checkpoint_index is not None
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "before": self.before.to_dict(),
            "action": self.action.to_dict(),
            "after": self.after.to_dict(),
            "response": self.response.to_dict() if self.response else None,
            "usage": dict(self.usage),
            "progress": self.progress.to_dict(),
            "provenance": self.provenance,
            "replay_status": self.replay_status,
            "reasoning_mode": self.reasoning_mode,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> QuestTransition:
        if not isinstance(payload, dict):
            raise ValueError(f"Transition must be an object, got {type(payload).__name__}; {MIGRATION_HINT}")
        for domain in ("before", "action", "after"):
            if domain not in payload:
                raise ValueError(f"Transition is missing '{domain}'; {MIGRATION_HINT}")
        response_payload = payload.get("response")
        response = None
        if isinstance(response_payload, dict) and response_payload:
            response = LLMResponse(**{k: v for k, v in response_payload.items() if k in LLMResponse.__annotations__})
        return cls(
            index=int(payload.get("index") or 0),
            before=QuestSnapshot.from_dict(payload.get("before") or {}),
            action=QuestAction.from_dict(payload.get("action") or {}),
            after=QuestSnapshot.from_dict(payload.get("after") or {}),
            response=response,
            usage=dict(payload.get("usage") or {}),
            progress=ProgressState.from_dict(payload.get("progress")),
            provenance=str(payload.get("provenance") or PROVENANCE_RUNTIME),
            replay_status=str(payload.get("replay_status") or REPLAY_PENDING),
            reasoning_mode=payload.get("reasoning_mode"),
        )


@dataclass
class ResumeLineage:
    """Link from a resumed run back to the record it continued."""

    source_run_id: Any
    source_path: str
    resumed_from_index: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> ResumeLineage | None:
        if not payload:
            return None
        return cls(
            source_run_id=payload.get("source_run_id"),
            source_path=str(payload.get("source_path") or ""),
            resumed_from_index=int(payload.get("resumed_from_index") or 0),
        )


@dataclass
class RunRecord:
    """Schema-v2 run record shared by ``run_summary.json`` and SQLite.

    The serialized form groups these fields into the canonical domains
    ``run``, ``quest``, ``treatment``, ``lineage``, ``terminal``, ``usage``,
    ``progress``, ``transcript_diagnostics``, and ``transitions``. Nothing is
    written or read at the top level except ``schema_version``.
    """

    run_id: Any
    quest_file: str
    quest_name: str
    quest_checksum: str
    quest_language: str
    engine_revision: str
    agent_id: str
    treatment: dict[str, Any]
    started_at: str | None = None
    ended_at: str | None = None
    run_duration: float | None = None
    benchmark_id: str | None = None
    lineage: ResumeLineage | None = None
    outcome: str | None = None
    reward: float = 0.0
    usage: dict[str, Any] = field(default_factory=dict)
    transcript_diagnostics: dict[str, Any] = field(default_factory=dict)
    progress: ProgressState = field(default_factory=ProgressState)
    terminal_snapshot: QuestSnapshot | None = None
    transitions: list[QuestTransition] = field(default_factory=list)
    schema_version: int = SCHEMA_VERSION

    @property
    def treatment_signature(self) -> str:
        return str(self.treatment.get("signature") or "")

    @property
    def is_resumable(self) -> bool:
        """Resumable runs carry a complete, deterministic engine lineage."""
        if self.outcome not in ("TRUNCATED",):
            return False
        if not self.transitions:
            return False
        if any(t.provenance != PROVENANCE_RUNTIME or not t.is_replayable for t in self.transitions):
            return False
        return self.transitions[-1].after.is_resumable

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run": {
                "id": self.run_id,
                "agent_id": self.agent_id,
                "started_at": self.started_at,
                "ended_at": self.ended_at,
                "duration": self.run_duration,
                "benchmark_id": self.benchmark_id,
            },
            "quest": {
                "file": self.quest_file,
                "name": self.quest_name,
                "checksum": self.quest_checksum,
                "language": self.quest_language,
                "engine_revision": self.engine_revision,
            },
            "treatment": self.treatment,
            "lineage": self.lineage.to_dict() if self.lineage else None,
            "terminal": {
                "outcome": self.outcome,
                "reward": self.reward,
                "snapshot": self.terminal_snapshot.to_dict() if self.terminal_snapshot else None,
            },
            "usage": self.usage,
            "progress": self.progress.to_dict(),
            "transcript_diagnostics": self.transcript_diagnostics,
            "transitions": [t.to_dict() for t in self.transitions],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RunRecord:
        """Rebuild a record, rejecting anything that is not a complete v2 document."""
        if not isinstance(payload, dict):
            raise ValueError(f"Run record must be an object, got {type(payload).__name__}; {MIGRATION_HINT}")

        version = payload.get("schema_version")
        if version != SCHEMA_VERSION:
            raise ValueError(f"Unsupported run record schema_version {version!r}; {MIGRATION_HINT}")

        missing = [domain for domain in RUN_RECORD_DOMAINS if domain not in payload]
        if missing:
            raise ValueError(f"Run record is missing canonical domain(s): {', '.join(missing)}; {MIGRATION_HINT}")

        run = _require_mapping(payload["run"], "run")
        quest = _require_mapping(payload["quest"], "quest")
        treatment = _require_mapping(payload["treatment"], "treatment")
        terminal = _require_mapping(payload["terminal"], "terminal")
        usage = _require_mapping(payload["usage"], "usage")
        progress = _require_mapping(payload["progress"], "progress")
        diagnostics = _require_mapping(payload["transcript_diagnostics"], "transcript_diagnostics")

        lineage_payload = payload["lineage"]
        if lineage_payload is not None and not isinstance(lineage_payload, dict):
            raise ValueError(f"Run record domain 'lineage' must be an object or null; {MIGRATION_HINT}")

        transitions_payload = payload["transitions"]
        if not isinstance(transitions_payload, list):
            raise ValueError(f"Run record domain 'transitions' must be a list; {MIGRATION_HINT}")

        terminal_snapshot = terminal.get("snapshot")
        if terminal_snapshot is not None and not isinstance(terminal_snapshot, dict):
            raise ValueError(f"Run record field 'terminal.snapshot' must be an object or null; {MIGRATION_HINT}")

        return cls(
            run_id=run.get("id"),
            quest_file=str(quest.get("file") or ""),
            quest_name=str(quest.get("name") or ""),
            quest_checksum=str(quest.get("checksum") or ""),
            quest_language=str(quest.get("language") or ""),
            engine_revision=str(quest.get("engine_revision") or ""),
            agent_id=str(run.get("agent_id") or ""),
            treatment=dict(treatment),
            started_at=run.get("started_at"),
            ended_at=run.get("ended_at"),
            run_duration=run.get("duration"),
            benchmark_id=run.get("benchmark_id"),
            lineage=ResumeLineage.from_dict(lineage_payload),
            outcome=terminal.get("outcome"),
            reward=float(terminal.get("reward") or 0.0),
            usage=dict(usage),
            transcript_diagnostics=dict(diagnostics),
            progress=ProgressState.from_dict(progress),
            terminal_snapshot=QuestSnapshot.from_dict(terminal_snapshot) if terminal_snapshot else None,
            transitions=[QuestTransition.from_dict(t) for t in transitions_payload],
        )


def load_run_record(path: str) -> RunRecord:
    """Load a schema-v2 ``run_summary.json`` from disk."""
    from pathlib import Path

    with open(Path(path), encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict):
        raise ValueError(f"Run record is not a JSON object: {path}")
    return RunRecord.from_dict(payload)
