#!/usr/bin/env python3
"""Convert a browser-exported human trace into a schema-v2 run_summary.json.

Restore events exported by the web player are preserved as restore transitions;
undone steps are never erased from the record.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from llm_quest_benchmark.core.logging import QuestLogger  # noqa: E402
from llm_quest_benchmark.core.provenance import quest_checksum  # noqa: E402
from llm_quest_benchmark.harnesses.specs import build_treatment  # noqa: E402
from llm_quest_benchmark.schemas.records import (  # noqa: E402
    PROVENANCE_RUNTIME,
    REPLAY_UNAVAILABLE,
    ProgressState,
    QuestAction,
    QuestSnapshot,
    QuestTransition,
    RunRecord,
)
from llm_quest_benchmark.schemas.response import LLMResponse  # noqa: E402

TRACE_SCHEMA = "human_trace_v2"
UNAVAILABLE = "unavailable"


def normalize_outcome(outcome: str | None) -> str:
    value = (outcome or "INCOMPLETE").upper()
    if value in {"WIN", "SUCCESS"}:
        return "SUCCESS"
    if value in {"FAIL", "DEAD", "FAILURE"}:
        return "FAILURE"
    return "INCOMPLETE"


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def duration_seconds(started_at: str | None, ended_at: str | None) -> float | None:
    start = parse_time(started_at)
    end = parse_time(ended_at)
    if not start or not end:
        return None
    return max(0.0, (end - start).total_seconds())


def make_run_id(trace: dict[str, Any]) -> str:
    quest_id = str(trace.get("quest_id") or trace.get("quest_title") or "quest")
    exported_at = trace.get("metadata", {}).get("exported_at") or trace.get("ended_at")
    if exported_at:
        safe_time = "".join(ch for ch in str(exported_at) if ch.isdigit())[:14]
    else:
        safe_time = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    safe_quest = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in quest_id)
    return f"human_web_{safe_quest}_{safe_time}"


def convert_snapshot(state: dict[str, Any] | None) -> QuestSnapshot:
    """Map an exported web state into a canonical snapshot."""
    if not isinstance(state, dict) or not state:
        return QuestSnapshot.unavailable()

    choices_map = state.get("choices") or {}
    choices = [
        {"id": "", "text": str(text)}
        for _, text in sorted(choices_map.items(), key=lambda item: int(item[0]))
    ]
    game_state = str(state.get("game_state") or "running")
    saving = state.get("saving") if isinstance(state.get("saving"), dict) else None
    return QuestSnapshot(
        location_id=str(state.get("location_id") or ""),
        observation=str(state.get("observation") or ""),
        choices=choices,
        params_state=[str(p) for p in (state.get("params") or [])],
        done=game_state not in ("running",),
        game_state=game_state,
        saving=saving,
        # The web player generates its own engine timestamp per jump, so choice
        # ids and transition timestamps are not observable in the browser.
        unavailable_fields=["choice_ids", "performed_at_ms"],
    )


def convert_transition(index: int, entry: dict[str, Any]) -> QuestTransition:
    action_payload = entry.get("action") or {}
    kind = str(action_payload.get("kind") or entry.get("kind") or "choose")

    if kind == "restore":
        action = QuestAction.restore(int(action_payload.get("checkpoint_index") or 1))
        response = None
    else:
        choice_index = action_payload.get("choice_index")
        action = QuestAction(
            kind="choose",
            choice_index=int(choice_index) if choice_index is not None else None,
            choice_id=None,
            performed_at_ms=action_payload.get("performed_at_ms"),
        )
        response = LLMResponse(
            action=action.choice_index or 1,
            reasoning="human selected in web UI",
            is_default=False,
            parse_mode="human_web",
        )

    return QuestTransition(
        index=index,
        before=convert_snapshot(entry.get("before")),
        action=action,
        after=convert_snapshot(entry.get("after")),
        response=response,
        usage={},
        progress=ProgressState(),
        provenance=PROVENANCE_RUNTIME,
        # Really executed, but the browser cannot supply the engine timestamp,
        # so the transition is not deterministically replayable.
        replay_status=REPLAY_UNAVAILABLE,
    )


def convert_trace(trace: dict[str, Any], source_trace: str | None = None) -> RunRecord:
    if trace.get("schema_version") != TRACE_SCHEMA:
        raise ValueError(f"expected schema_version {TRACE_SCHEMA}")
    if trace.get("source") != "web_play":
        raise ValueError("expected source web_play")

    transitions = [
        convert_transition(index, entry)
        for index, entry in enumerate(trace.get("transitions") or [], start=1)
        if isinstance(entry, dict)
    ]
    quest_id = str(trace.get("quest_id") or "unknown")
    quest_file = f"quests/{quest_id}.qm"
    checksum = quest_checksum(quest_file) if Path(quest_file).exists() else UNAVAILABLE

    treatment = build_treatment(
        harness="human",
        model="human",
        temperature=0.0,
        system_template="none",
    ).to_dict()

    record = RunRecord(
        run_id=make_run_id(trace),
        quest_file=quest_file,
        quest_name=str(trace.get("quest_title") or quest_id),
        quest_checksum=checksum,
        quest_language="rus" if trace.get("quest_lang") == "ru" else "eng",
        engine_revision=UNAVAILABLE,
        agent_id="human_web",
        treatment=treatment,
        started_at=trace.get("started_at"),
        ended_at=trace.get("ended_at"),
        run_duration=duration_seconds(trace.get("started_at"), trace.get("ended_at")),
        outcome=normalize_outcome(trace.get("outcome")),
        reward=0.0,
        transitions=transitions,
        terminal_snapshot=transitions[-1].after if transitions else None,
    )
    record.usage = QuestLogger.aggregate_usage(transitions)
    record.transcript_diagnostics = QuestLogger.calculate_metrics(transitions, record.outcome)
    record.transcript_diagnostics["source"] = "web_play_human_trace"
    if source_trace:
        record.transcript_diagnostics["source_trace"] = source_trace
    return record


def write_summary(record: RunRecord, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Browser-exported human_trace_*.json")
    parser.add_argument("--output", required=True, type=Path, help="Destination run_summary.json")
    args = parser.parse_args()

    trace = json.loads(args.input.read_text(encoding="utf-8"))
    record = convert_trace(trace, source_trace=str(args.input))
    write_summary(record, args.output)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
