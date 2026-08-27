"""One-time migration of legacy records into schema v2.

This module is the only legacy reader in the codebase. It never fabricates a
missing action, timestamp, parameter state, engine saving, or post-state:
unknowable fields are marked unavailable and the resulting transitions are
rejected for resume.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from llm_quest_benchmark.core.logging import QuestLogger, ensure_v2_schema
from llm_quest_benchmark.core.provenance import quest_checksum
from llm_quest_benchmark.harnesses.specs import HARNESS_SPECS, HarnessTreatment, build_treatment
from llm_quest_benchmark.schemas.records import (
    PROVENANCE_LEGACY_MAPPED,
    REPLAY_UNAVAILABLE,
    SCHEMA_VERSION,
    ProgressState,
    QuestAction,
    QuestSnapshot,
    QuestTransition,
    RunRecord,
)
from llm_quest_benchmark.schemas.response import LLMResponse

UNAVAILABLE = "unavailable"
UNKNOWN = "unknown"
LEGACY_RUN_COLUMNS = (
    "id",
    "quest_file",
    "quest_name",
    "start_time",
    "end_time",
    "agent_id",
    "agent_config",
    "outcome",
    "reward",
    "run_duration",
    "benchmark_id",
)


@dataclass
class MigrationReport:
    """Summary of one migration invocation."""

    source: str
    output: str
    kind: str
    runs_migrated: int = 0
    transitions_migrated: int = 0
    resumable_runs: int = 0
    skipped: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "output": self.output,
            "kind": self.kind,
            "runs_migrated": self.runs_migrated,
            "transitions_migrated": self.transitions_migrated,
            "resumable_runs": self.resumable_runs,
            "skipped": self.skipped,
        }


# ---- shared helpers --------------------------------------------------------


def _safe_json_load(value: Any, default: Any = None) -> Any:
    if value is None or value == "":
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


def _safe_int(value: Any) -> int | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _choices_from_list(choices: Any) -> list[dict[str, str]]:
    """Legacy SQLite stored choices as [{id, text}]; ids are engine jump ids."""
    if not isinstance(choices, list):
        return []
    return [{"id": str(c.get("id", "")), "text": str(c.get("text", ""))} for c in choices if isinstance(c, dict)]


def _choices_from_map(choices: Any) -> list[dict[str, str]]:
    """Compact JSON stored choices as {index: text}; engine jump ids are lost."""
    if not isinstance(choices, dict):
        return []
    ordered = sorted(choices.items(), key=lambda item: _safe_int(item[0]) or 0)
    return [{"id": "", "text": str(text)} for _, text in ordered]


def _legacy_snapshot(
    location_id: Any,
    observation: Any,
    choices: list[dict[str, str]],
    params_state: list[str] | None,
    game_state: str = "running",
    done: bool = False,
    reward: float = 0.0,
) -> QuestSnapshot:
    """Build a before/after snapshot from legacy fields, marking what is lost."""
    missing = ["saving"]
    if params_state is None:
        missing.append("params_state")
    if choices and not any(choice["id"] for choice in choices):
        missing.append("choice_ids")
    return QuestSnapshot(
        location_id=str(location_id if location_id is not None else ""),
        observation=str(observation or ""),
        choices=choices,
        params_state=list(params_state or []),
        reward=reward,
        done=done,
        game_state=game_state,
        saving=None,
        unavailable_fields=missing,
    )


def _legacy_treatment(agent_config: Any) -> HarnessTreatment:
    """Derive the treatment from a legacy agent config and the canonical registry."""
    config = agent_config if isinstance(agent_config, dict) else {}
    harness = str(config.get("harness") or "")
    model = str(config.get("model") or UNAVAILABLE)
    temperature = config.get("temperature")
    try:
        temperature = float(temperature) if temperature is not None else 0.0
    except (TypeError, ValueError):
        temperature = 0.0

    if harness in HARNESS_SPECS:
        return build_treatment(
            harness=harness,
            model=model,
            temperature=temperature,
            system_template=str(config.get("system_template") or UNAVAILABLE),
            knob_values={"compaction_interval": config.get("compaction_interval")},
        )
    # No compatibility alias: an unresolvable configuration stays explicitly
    # unknown. The recorded agent id is preserved on the run, not folded into
    # a guessed treatment.
    return HarnessTreatment.unknown(harness or UNKNOWN, model, temperature)


def _legacy_response(payload: Any, action_index: int | None) -> LLMResponse | None:
    if not isinstance(payload, dict):
        return None
    resolved_action = _safe_int(payload.get("action")) or action_index or 1
    return LLMResponse(
        action=resolved_action,
        analysis=payload.get("analysis"),
        reasoning=payload.get("reasoning"),
        memo=payload.get("memo"),
        tool_calls=payload.get("tool_calls"),
        tool_results=payload.get("tool_results"),
        is_default=bool(payload.get("is_default", False)),
        parse_mode=payload.get("parse_mode"),
        prompt_tokens=_safe_int(payload.get("prompt_tokens")),
        completion_tokens=_safe_int(payload.get("completion_tokens")),
        total_tokens=_safe_int(payload.get("total_tokens")),
        estimated_cost_usd=payload.get("estimated_cost_usd"),
    )


def _usage_from_response(response: LLMResponse | None) -> dict[str, Any]:
    if response is None:
        return {}
    return {
        "prompt_tokens": response.prompt_tokens or 0,
        "completion_tokens": response.completion_tokens or 0,
        "total_tokens": response.total_tokens or 0,
        "estimated_cost_usd": response.estimated_cost_usd,
    }


def _legacy_action(choice_index: int | None, choices: list[dict[str, str]]) -> QuestAction:
    """Map a legacy action index; ids and timestamps are never invented."""
    choice_id = None
    if choice_index is not None and 1 <= choice_index <= len(choices):
        choice_id = choices[choice_index - 1]["id"] or None
    return QuestAction(
        kind="choose",
        choice_index=choice_index,
        choice_id=choice_id,
        performed_at_ms=None,
    )


def _build_transitions(
    rows: list[dict[str, Any]],
    final_state: dict[str, Any] | None,
) -> list[QuestTransition]:
    """Map ordered legacy decision rows into v2 transitions.

    Each legacy row records the state *before* its action, so row ``i + 1`` is
    the observed post-state of transition ``i`` when their step numbers are
    consecutive. A trailing logger-only terminal row is treated as terminal
    state, not as an executed action.
    """
    terminal_row: dict[str, Any] | None = None
    if rows and not rows[-1]["choices"]:
        terminal_row = rows[-1]
        rows = rows[:-1]

    transitions: list[QuestTransition] = []
    for i, row in enumerate(rows):
        before = _legacy_snapshot(
            location_id=row["location_id"],
            observation=row["observation"],
            choices=row["choices"],
            params_state=row.get("params_state"),
        )

        next_row = rows[i + 1] if i + 1 < len(rows) else terminal_row
        after = QuestSnapshot.unavailable()
        structurally_next = (
            next_row is not None
            and _safe_int(next_row.get("step")) is not None
            and _safe_int(row.get("step")) is not None
            and _safe_int(next_row["step"]) == _safe_int(row["step"]) + 1
        )
        if structurally_next:
            after = _legacy_snapshot(
                location_id=next_row["location_id"],
                observation=next_row["observation"],
                choices=next_row["choices"],
                params_state=next_row.get("params_state"),
                done=next_row is terminal_row,
                game_state="running" if next_row is not terminal_row else UNAVAILABLE,
            )
        if i == len(rows) - 1 and isinstance(final_state, dict) and final_state:
            after = _legacy_snapshot(
                location_id=final_state.get("location_id"),
                observation=final_state.get("text") or final_state.get("observation"),
                choices=_choices_from_list(final_state.get("choices")),
                params_state=final_state.get("params_state"),
                done=bool(final_state.get("done", False)),
                reward=float(final_state.get("reward") or 0.0),
                game_state="running" if not final_state.get("done") else UNAVAILABLE,
            )

        transitions.append(
            QuestTransition(
                index=i + 1,
                before=before,
                action=row["action"],
                after=after,
                response=row.get("response"),
                usage=_usage_from_response(row.get("response")),
                progress=ProgressState(current=0.0, maximum=100.0, manifest=None),
                provenance=PROVENANCE_LEGACY_MAPPED,
                replay_status=REPLAY_UNAVAILABLE,
                reasoning_mode=None,
            )
        )
    return transitions


def _terminal_snapshot(rows: list[dict[str, Any]], final_state: dict[str, Any] | None) -> QuestSnapshot:
    if isinstance(final_state, dict) and final_state:
        return _legacy_snapshot(
            location_id=final_state.get("location_id"),
            observation=final_state.get("text") or final_state.get("observation"),
            choices=_choices_from_list(final_state.get("choices")),
            params_state=final_state.get("params_state"),
            done=bool(final_state.get("done", False)),
            reward=float(final_state.get("reward") or 0.0),
            game_state=UNAVAILABLE,
        )
    if rows and not rows[-1]["choices"]:
        row = rows[-1]
        return _legacy_snapshot(
            location_id=row["location_id"],
            observation=row["observation"],
            choices=[],
            params_state=row.get("params_state"),
            done=True,
            game_state=UNAVAILABLE,
        )
    return QuestSnapshot.unavailable()


def _build_record(
    *,
    run_id: Any,
    quest_file: str,
    quest_name: str,
    start_time: Any,
    end_time: Any,
    run_duration: Any,
    agent_id: str,
    agent_config: Any,
    outcome: str | None,
    reward: Any,
    benchmark_id: str | None,
    rows: list[dict[str, Any]],
    final_state: dict[str, Any] | None,
) -> RunRecord:
    treatment = _legacy_treatment(agent_config)
    transitions = _build_transitions(rows, final_state)

    checksum = UNAVAILABLE
    if quest_file and Path(quest_file).exists():
        checksum = quest_checksum(quest_file)

    record = RunRecord(
        run_id=run_id,
        quest_file=quest_file or UNAVAILABLE,
        quest_name=quest_name or (Path(quest_file).stem if quest_file else UNAVAILABLE),
        quest_checksum=checksum,
        quest_language=UNAVAILABLE,
        engine_revision=UNAVAILABLE,
        agent_id=agent_id or UNAVAILABLE,
        treatment=treatment.to_dict(),
        started_at=str(start_time) if start_time else None,
        ended_at=str(end_time) if end_time else None,
        run_duration=float(run_duration) if run_duration not in (None, "") else None,
        benchmark_id=benchmark_id,
        outcome=outcome,
        reward=float(reward or 0.0),
        transitions=transitions,
        terminal_snapshot=_terminal_snapshot(rows, final_state),
        schema_version=SCHEMA_VERSION,
    )
    record.usage = QuestLogger.aggregate_usage(transitions)
    record.transcript_diagnostics = QuestLogger.calculate_metrics(transitions, outcome)
    record.transcript_diagnostics["migrated_from"] = "legacy"
    return record


# ---- legacy JSON -----------------------------------------------------------


def _rows_from_legacy_json(steps: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        choices = _choices_from_map(step.get("choices"))
        decision = step.get("llm_decision") if isinstance(step.get("llm_decision"), dict) else {}
        choice_map = decision.get("choice") if isinstance(decision.get("choice"), dict) else {}
        choice_index = _safe_int(next(iter(choice_map), None)) if choice_map else None
        rows.append(
            {
                "step": _safe_int(step.get("step")),
                "location_id": step.get("location_id"),
                "observation": step.get("observation"),
                "choices": choices,
                "params_state": step.get("params") if isinstance(step.get("params"), list) else None,
                "action": _legacy_action(choice_index, choices),
                "response": _legacy_response(decision, choice_index),
            }
        )
    return rows


def migrate_legacy_json(payload: dict[str, Any]) -> RunRecord:
    """Map one legacy ``run_summary.json`` document into a v2 record."""
    if payload.get("schema_version") == SCHEMA_VERSION:
        raise ValueError("Record is already schema v2; migration is a one-time legacy conversion.")

    rows = _rows_from_legacy_json(payload.get("steps") or [])
    return _build_record(
        run_id=payload.get("run_id"),
        quest_file=str(payload.get("quest_file") or ""),
        quest_name=str(payload.get("quest_name") or ""),
        start_time=payload.get("start_time"),
        end_time=payload.get("end_time"),
        run_duration=payload.get("run_duration"),
        agent_id=str(payload.get("agent_id") or ""),
        agent_config=payload.get("agent_config"),
        outcome=payload.get("outcome"),
        reward=payload.get("reward"),
        benchmark_id=payload.get("benchmark_id"),
        rows=rows,
        final_state=payload.get("final_state") if isinstance(payload.get("final_state"), dict) else None,
    )


# ---- legacy SQLite ---------------------------------------------------------


def _rows_from_legacy_sqlite(conn: sqlite3.Connection, run_id: Any) -> list[dict[str, Any]]:
    cursor = conn.execute(
        """
        SELECT step, location_id, observation, choices, action, llm_response
        FROM steps
        WHERE run_id = ?
        ORDER BY step
        """,
        (run_id,),
    )
    rows: list[dict[str, Any]] = []
    for step, location_id, observation, choices_json, action, llm_response in cursor.fetchall():
        choices = _choices_from_list(_safe_json_load(choices_json, []))
        # SQLite stores the runner-clamped action, which compact JSON could not
        # distinguish from a model proposal, so it wins whenever it is present.
        choice_index = _safe_int(action)
        response_payload = _safe_json_load(llm_response)
        rows.append(
            {
                "step": _safe_int(step),
                "location_id": location_id,
                "observation": observation,
                "choices": choices,
                "params_state": None,
                "action": _legacy_action(choice_index, choices),
                "response": _legacy_response(response_payload, choice_index),
            }
        )
    return rows


def _legacy_run_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    cursor = conn.execute("PRAGMA table_info(runs)")
    columns = {row[1] for row in cursor.fetchall()}
    if not columns:
        raise ValueError("Source database has no 'runs' table")
    if "schema_version" in columns:
        raise ValueError("Source database is already schema v2; migration is a one-time legacy conversion.")

    selected = [name for name in LEGACY_RUN_COLUMNS if name in columns]
    rows = conn.execute(f"SELECT {', '.join(selected)} FROM runs ORDER BY id").fetchall()
    return [dict(zip(selected, row, strict=True)) for row in rows]


def migrate_legacy_sqlite(source: Path, output: Path) -> MigrationReport:
    """Convert a legacy metrics database into a fresh v2 database."""
    report = MigrationReport(source=str(source), output=str(output), kind="sqlite")
    if output.exists():
        raise ValueError(f"Migration output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    src = sqlite3.connect(source)
    dst = sqlite3.connect(output)
    try:
        ensure_v2_schema(dst)
        for run in _legacy_run_rows(src):
            rows = _rows_from_legacy_sqlite(src, run.get("id"))
            record = _build_record(
                run_id=run.get("id"),
                quest_file=str(run.get("quest_file") or ""),
                quest_name=str(run.get("quest_name") or ""),
                start_time=run.get("start_time"),
                end_time=run.get("end_time"),
                run_duration=run.get("run_duration"),
                agent_id=str(run.get("agent_id") or ""),
                agent_config=_safe_json_load(run.get("agent_config")),
                outcome=run.get("outcome"),
                reward=run.get("reward"),
                benchmark_id=run.get("benchmark_id"),
                rows=rows,
                final_state=None,
            )
            _insert_record(dst, record)
            report.runs_migrated += 1
            report.transitions_migrated += len(record.transitions)
            if record.is_resumable:
                report.resumable_runs += 1
        dst.commit()
    finally:
        src.close()
        dst.close()
    return report


def _insert_record(conn: sqlite3.Connection, record: RunRecord) -> None:
    cursor = conn.execute(
        """
        INSERT INTO runs (
            schema_version, quest_file, quest_name, quest_checksum, quest_language,
            engine_revision, agent_id, treatment, treatment_signature, benchmark_id,
            lineage, start_time, end_time, run_duration, outcome, reward,
            usage, transcript_diagnostics, progress, terminal_snapshot
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.schema_version,
            record.quest_file,
            record.quest_name,
            record.quest_checksum,
            record.quest_language,
            record.engine_revision,
            record.agent_id,
            json.dumps(record.treatment, ensure_ascii=False),
            record.treatment_signature,
            record.benchmark_id,
            None,
            record.started_at,
            record.ended_at,
            record.run_duration,
            record.outcome,
            record.reward,
            json.dumps(record.usage, ensure_ascii=False),
            json.dumps(record.transcript_diagnostics, ensure_ascii=False),
            json.dumps(record.progress.to_dict(), ensure_ascii=False),
            json.dumps(record.terminal_snapshot.to_dict(), ensure_ascii=False) if record.terminal_snapshot else None,
        ),
    )
    new_run_id = cursor.lastrowid
    for transition in record.transitions:
        payload = transition.to_dict()
        conn.execute(
            """
            INSERT INTO transitions (
                run_id, transition_index, before_state, action, after_state,
                response, usage, progress, provenance, replay_status, reasoning_mode
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_run_id,
                transition.index,
                json.dumps(payload["before"], ensure_ascii=False),
                json.dumps(payload["action"], ensure_ascii=False),
                json.dumps(payload["after"], ensure_ascii=False),
                json.dumps(payload["response"], ensure_ascii=False) if payload["response"] else None,
                json.dumps(payload["usage"], ensure_ascii=False),
                json.dumps(payload["progress"], ensure_ascii=False),
                transition.provenance,
                transition.replay_status,
                transition.reasoning_mode,
            ),
        )


# ---- entry point -----------------------------------------------------------


def migrate_json_tree(source: Path, output: Path) -> MigrationReport:
    """Convert one legacy run summary, or a tree of them, into v2 JSON."""
    report = MigrationReport(source=str(source), output=str(output), kind="json")

    if source.is_file():
        payloads = [(source, source.name)]
        output_root = output if output.suffix == ".json" else output / source.name
        single_file = True
    else:
        payloads = [(path, str(path.relative_to(source))) for path in sorted(source.rglob("run_summary.json"))]
        output_root = output
        single_file = False

    if not payloads:
        raise ValueError(f"No legacy run_summary.json files found under {source}")

    for path, relative in payloads:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
        try:
            record = migrate_legacy_json(payload)
        except ValueError as exc:
            report.skipped.append(f"{path}: {exc}")
            continue

        destination = output_root if single_file else output_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        with open(destination, "w", encoding="utf-8") as f:
            json.dump(record.to_dict(), f, indent=2, ensure_ascii=False)

        report.runs_migrated += 1
        report.transitions_migrated += len(record.transitions)
        if record.is_resumable:
            report.resumable_runs += 1

    return report


def migrate_records(source: str | Path, output: str | Path) -> MigrationReport:
    """Migrate a legacy JSON tree or SQLite database into a v2 destination."""
    source_path = Path(source)
    output_path = Path(output)
    if not source_path.exists():
        raise FileNotFoundError(f"Migration source not found: {source_path}")

    if source_path.is_dir() or source_path.suffix == ".json":
        return migrate_json_tree(source_path, output_path)
    return migrate_legacy_sqlite(source_path, output_path)
