#!/usr/bin/env python3
"""Convert a browser-exported human trace into run_summary.json format."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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
        safe_time = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    safe_quest = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in quest_id)
    return f"human_web_{safe_quest}_{safe_time}"


def convert_step(step: dict[str, Any]) -> dict[str, Any]:
    decision = step.get("human_decision") or {}
    choice_index = str(decision.get("choice_index") or "")
    choice_text = str(decision.get("choice_text") or "")
    choices = {str(k): str(v) for k, v in (step.get("choices") or {}).items()}
    if not choice_text and choice_index in choices:
        choice_text = choices[choice_index]

    return {
        "step": step.get("step"),
        "location_id": step.get("location_id"),
        "observation": step.get("observation") or "",
        "params": step.get("params") or [],
        "choices": choices,
        "llm_decision": {
            "analysis": "",
            "reasoning": "human selected in web UI",
            "is_default": False,
            "choice": {choice_index: choice_text} if choice_index else {},
        },
        "human_decision": decision,
    }


def convert_trace(trace: dict[str, Any], source_trace: str | None = None) -> dict[str, Any]:
    if trace.get("schema_version") != "human_trace_v1":
        raise ValueError("expected schema_version human_trace_v1")
    if trace.get("source") != "web_play":
        raise ValueError("expected source web_play")

    steps = [convert_step(step) for step in trace.get("steps") or []]
    outcome = normalize_outcome(trace.get("outcome"))
    quest_name = trace.get("quest_title") or trace.get("quest_id") or "unknown"

    summary: dict[str, Any] = {
        "run_id": make_run_id(trace),
        "quest_name": quest_name,
        "quest_id": trace.get("quest_id"),
        "agent_id": "human_web",
        "agent_mode": "human",
        "model": "human",
        "outcome": outcome,
        "run_duration": duration_seconds(trace.get("started_at"), trace.get("ended_at")),
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0,
            "priced_steps": 0,
        },
        "steps": steps,
        "terminal": trace.get("terminal") or {},
        "source": "web_play_human_trace",
    }
    if source_trace:
        summary["source_trace"] = source_trace
    return summary


def write_summary(summary: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Browser-exported human_trace_*.json")
    parser.add_argument("--output", required=True, type=Path, help="Destination run_summary.json")
    args = parser.parse_args()

    trace = json.loads(args.input.read_text(encoding="utf-8"))
    summary = convert_trace(trace, source_trace=str(args.input))
    write_summary(summary, args.output)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
