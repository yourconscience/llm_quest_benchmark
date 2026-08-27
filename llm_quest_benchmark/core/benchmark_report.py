"""Markdown report generator for benchmark runs."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from llm_quest_benchmark.schemas.records import QuestTransition, RunRecord


@dataclass
class RunInsight:
    """Parsed and enriched benchmark run data."""

    benchmark_id: str
    run_id: int
    model: str
    harness: str
    treatment_signature: str
    progress: float
    quest_name: str
    outcome: str
    duration: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float | None
    priced_steps: int
    decision_steps: int
    default_decision_steps: int
    selected_choice: str | None
    selected_reasoning: str | None
    selected_analysis: str | None
    selected_observation: str | None
    summary_path: Path | None


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _shorten(text: str | None, limit: int = 180) -> str | None:
    if not text:
        return text
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3] + "..."


def _treatment(run_row: dict[str, Any]) -> dict[str, Any]:
    """Read the canonical treatment recorded on a schema-v2 run row."""
    raw = run_row.get("treatment")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _extract_model(run_row: dict[str, Any]) -> str:
    model = _treatment(run_row).get("model")
    if model:
        return str(model)
    return str(run_row.get("agent_id") or "unknown")


def _extract_harness(run_row: dict[str, Any]) -> str:
    harness = _treatment(run_row).get("harness")
    return str(harness) if harness else ""


def _harnesses_by_model(insights: list[RunInsight]) -> dict[str, set[str]]:
    """Map each insight's model to the set of distinct harness values run under it."""
    by_model: dict[str, set[str]] = {}
    for insight in insights:
        by_model.setdefault(insight.model, set()).add(insight.harness or "")
    return by_model


def _group_label(model: str, harness: str, harnesses_by_model: dict[str, set[str]] | None = None) -> str:
    """Stable per-agent-variant label matching executors.benchmark._result_group_label.

    Keeps this report's grouping key format identical to
    calculate_summary_stats's, since render_benchmark_report looks up
    per-group outcome overrides from benchmark_summary.json's
    summary_stats.models by this same key. Stays the bare model name --
    preserving prior report output exactly -- whenever that model only ran
    under one harness among the insights being summarized.
    """
    if not harness or harness == "human" or harness.startswith("random_choice"):
        return model
    if harnesses_by_model is not None and len(harnesses_by_model.get(model, set())) <= 1:
        return model
    return f"{model} [{harness}]"


def _extract_last_decision(
    transitions: list[QuestTransition],
) -> tuple[str | None, str | None, str | None, str | None, int, int]:
    decision_steps = 0
    default_decisions = 0
    last_choice = None
    last_reasoning = None
    last_analysis = None
    last_observation = None

    for transition in transitions:
        choices = transition.before.choices
        if len(choices) <= 1:
            continue
        decision_steps += 1
        response = transition.response
        if response is not None and response.is_default:
            default_decisions += 1

        if transition.action.is_restore:
            last_choice = f"restore checkpoint {transition.action.checkpoint_index}"
        else:
            index = transition.action.choice_index
            text = choices[index - 1]["text"] if index and 1 <= index <= len(choices) else ""
            last_choice = f"{index}: {text}"

        last_reasoning = _shorten(response.reasoning if response else None)
        last_analysis = _shorten(response.analysis if response else None)
        last_observation = _shorten(transition.before.observation, 220)

    return (
        last_choice,
        last_reasoning,
        last_analysis,
        last_observation,
        decision_steps,
        default_decisions,
    )


def _resolve_run_summary_path(run_row: dict[str, Any]) -> Path | None:
    run_id = run_row.get("id")
    quest_name = run_row.get("quest_name")
    agent_id = run_row.get("agent_id")
    if run_id is None or not quest_name or not agent_id:
        return None
    return Path("results") / str(agent_id) / str(quest_name) / f"run_{run_id}" / "run_summary.json"


def _parse_run_insight(benchmark_id: str, run_row: dict[str, Any]) -> RunInsight:
    summary_path = _resolve_run_summary_path(run_row)
    run_summary = _load_json(summary_path) if summary_path else None

    run_id = int(run_row.get("id") or -1)
    # Keep DB row outcome/duration as canonical benchmark truth.
    # run_summary can drift for timeout/error cases when background execution finishes later.
    outcome = str(run_row.get("outcome") or "UNKNOWN")
    duration = float(run_row.get("run_duration") or 0.0)
    usage = run_row.get("usage") if isinstance(run_row.get("usage"), dict) else {}
    progress = run_row.get("progress") if isinstance(run_row.get("progress"), dict) else {}
    transitions: list[QuestTransition] = []

    if isinstance(run_summary, dict):
        record = RunRecord.from_dict(run_summary)
        usage = usage or record.usage
        progress = progress or record.progress.to_dict()
        transitions = record.transitions

    selected_choice, selected_reasoning, selected_analysis, selected_observation, decision_steps, default_decisions = (
        _extract_last_decision(transitions)
    )

    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))
    priced_steps = int(usage.get("priced_steps") or 0)
    estimated_cost = usage.get("estimated_cost_usd")
    if estimated_cost is not None:
        estimated_cost = float(estimated_cost)

    return RunInsight(
        benchmark_id=benchmark_id,
        run_id=run_id,
        model=_extract_model(run_row),
        harness=_extract_harness(run_row),
        treatment_signature=str(run_row.get("treatment_signature") or _treatment(run_row).get("signature") or ""),
        progress=float(progress.get("current") or 0.0),
        quest_name=str(run_row.get("quest_name") or "unknown"),
        outcome=outcome,
        duration=duration,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost,
        priced_steps=priced_steps,
        decision_steps=decision_steps,
        default_decision_steps=default_decisions,
        selected_choice=selected_choice,
        selected_reasoning=selected_reasoning,
        selected_analysis=selected_analysis,
        selected_observation=selected_observation,
        summary_path=summary_path if summary_path and summary_path.exists() else None,
    )


def _latest_benchmark_ids(output_dir: Path, limit: int = 1) -> list[str]:
    if not output_dir.exists():
        return []
    benchmark_dirs = [p for p in output_dir.iterdir() if p.is_dir()]
    benchmark_dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [p.name for p in benchmark_dirs[:limit]]


def _collect_insights(benchmark_id: str, output_dir: Path) -> list[RunInsight]:
    summary_path = output_dir / benchmark_id / "benchmark_summary.json"
    benchmark_summary = _load_json(summary_path)
    if not benchmark_summary:
        return []
    db_runs = benchmark_summary.get("db_runs") if isinstance(benchmark_summary.get("db_runs"), list) else []
    return [_parse_run_insight(benchmark_id, row) for row in db_runs if isinstance(row, dict)]


def _load_benchmark_summary_doc(benchmark_id: str, output_dir: Path) -> dict[str, Any] | None:
    summary_path = output_dir / benchmark_id / "benchmark_summary.json"
    return _load_json(summary_path)


def _format_benchmark_summary(insights: list[RunInsight]) -> dict[str, Any]:
    outcomes = Counter(i.outcome for i in insights)
    total = len(insights)
    success = outcomes.get("SUCCESS", 0)
    failure = outcomes.get("FAILURE", 0)
    timeout = outcomes.get("TIMEOUT", 0)
    error = outcomes.get("ERROR", 0)
    total_tokens = sum(i.total_tokens for i in insights)
    total_cost = sum((i.estimated_cost_usd or 0.0) for i in insights)
    priced_runs = sum(1 for i in insights if i.estimated_cost_usd is not None)
    avg_duration = (sum(i.duration for i in insights) / total) if total else 0.0

    return {
        "total": total,
        "success": success,
        "failure": failure,
        "timeout": timeout,
        "error": error,
        "success_rate": (success / total * 100.0) if total else 0.0,
        "total_tokens": total_tokens,
        "total_cost": total_cost if priced_runs else None,
        "priced_runs": priced_runs,
        "avg_duration": avg_duration,
    }


def _format_model_summary(
    insights: list[RunInsight],
    outcome_overrides: dict[str, dict[str, Any]] | None = None,
    harnesses_by_model: dict[str, set[str]] | None = None,
) -> dict[str, dict[str, Any]]:
    if harnesses_by_model is None:
        harnesses_by_model = _harnesses_by_model(insights)

    grouped: dict[str, list[RunInsight]] = defaultdict(list)
    for insight in insights:
        grouped[_group_label(insight.model, insight.harness, harnesses_by_model)].append(insight)

    model_summary: dict[str, dict[str, Any]] = {}
    for group, rows in sorted(grouped.items()):
        outcomes = Counter(r.outcome for r in rows)
        total = len(rows)
        success = outcomes.get("SUCCESS", 0)
        total_tokens = sum(r.total_tokens for r in rows)
        total_cost = sum((r.estimated_cost_usd or 0.0) for r in rows)
        priced_runs = sum(1 for r in rows if r.estimated_cost_usd is not None)
        decision_steps = sum(r.decision_steps for r in rows)
        default_steps = sum(r.default_decision_steps for r in rows)

        override = (outcome_overrides or {}).get(group, {})
        success_override = override.get("success")
        failure_override = override.get("failed")
        timeout_override = override.get("timeouts")
        error_override = override.get("errors")
        success_rate_override = override.get("success_rate")
        total_override = override.get("total_runs")

        if total_override is not None:
            total = int(total_override)
        if success_override is not None:
            success = int(success_override)
        failure = int(failure_override) if failure_override is not None else outcomes.get("FAILURE", 0)
        timeout = int(timeout_override) if timeout_override is not None else outcomes.get("TIMEOUT", 0)
        error = int(error_override) if error_override is not None else outcomes.get("ERROR", 0)
        if success_rate_override is not None:
            success_rate = float(success_rate_override)
            if success_rate <= 1.0:
                success_rate *= 100.0
        else:
            success_rate = (success / total * 100.0) if total else 0.0

        model_summary[group] = {
            "runs": total,
            "success": success,
            "failure": failure,
            "timeout": timeout,
            "error": error,
            "success_rate": success_rate,
            "tokens": total_tokens,
            "cost": total_cost if priced_runs else None,
            "default_rate": (default_steps / decision_steps * 100.0) if decision_steps else 0.0,
            "avg_progress": (sum(r.progress for r in rows) / len(rows)) if rows else 0.0,
            "treatment_signature": rows[0].treatment_signature if rows else "",
        }
    return model_summary


def _format_failure_rows(insights: list[RunInsight], limit: int = 12) -> list[RunInsight]:
    failed = [i for i in insights if i.outcome in {"FAILURE", "TIMEOUT", "ERROR"}]
    failed.sort(key=lambda row: (row.outcome, row.model, row.harness, row.quest_name, row.run_id))
    return failed[:limit]


def render_benchmark_report(
    benchmark_ids: list[str] | None = None,
    output_dir: str = "results/benchmarks",
) -> tuple[str, list[str]]:
    """Render markdown report for one or multiple benchmark IDs."""
    output_root = Path(output_dir)
    selected_ids = benchmark_ids or _latest_benchmark_ids(output_root, limit=1)
    selected_ids = [b for b in selected_ids if b]
    if not selected_ids:
        raise ValueError(f"No benchmark directories found under {output_root}")

    sections: list[str] = []
    sections.append("# Benchmark Report")
    sections.append("")
    sections.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    sections.append("")

    all_insights: list[RunInsight] = []
    for benchmark_id in selected_ids:
        benchmark_doc = _load_benchmark_summary_doc(benchmark_id, output_root)
        insights = _collect_insights(benchmark_id, output_root)
        if not insights:
            sections.append(f"## {benchmark_id}")
            sections.append("")
            sections.append("No benchmark data found.")
            sections.append("")
            continue

        all_insights.extend(insights)
        summary = _format_benchmark_summary(insights)
        model_overrides = {}
        if isinstance(benchmark_doc, dict):
            summary_stats = benchmark_doc.get("summary_stats")
            if isinstance(summary_stats, dict):
                summary["total"] = int(summary_stats.get("total_runs", summary["total"]))
                summary["success"] = int(summary_stats.get("total_success", summary["success"]))
                summary["failure"] = int(summary_stats.get("total_failures", summary["failure"]))
                summary["timeout"] = int(summary_stats.get("total_timeouts", summary["timeout"]))
                summary["error"] = int(summary_stats.get("total_errors", summary["error"]))
                raw_success_rate = float(summary_stats.get("success_rate", summary["success_rate"] / 100.0))
                summary["success_rate"] = raw_success_rate * 100.0 if raw_success_rate <= 1.0 else raw_success_rate
                model_overrides = summary_stats.get("models") if isinstance(summary_stats.get("models"), dict) else {}

        harnesses_by_model = _harnesses_by_model(insights)
        model_summary = _format_model_summary(
            insights, outcome_overrides=model_overrides, harnesses_by_model=harnesses_by_model
        )
        failure_rows = _format_failure_rows(insights)
        breakdown_label = "Agent" if any("[" in group for group in model_summary) else "Model"

        sections.append(f"## {benchmark_id}")
        sections.append("")
        sections.append("| Metric | Value |")
        sections.append("|---|---:|")
        sections.append(f"| Total runs | {summary['total']} |")
        sections.append(f"| Success | {summary['success']} |")
        sections.append(f"| Failure | {summary['failure']} |")
        sections.append(f"| Timeout | {summary['timeout']} |")
        sections.append(f"| Error | {summary['error']} |")
        sections.append(f"| Success rate | {summary['success_rate']:.1f}% |")
        sections.append(f"| Avg duration | {summary['avg_duration']:.2f}s |")
        sections.append(f"| Total tokens | {summary['total_tokens']} |")
        if summary["total_cost"] is None:
            sections.append("| Estimated cost (USD) | n/a |")
        else:
            sections.append(f"| Estimated cost (USD) | {summary['total_cost']:.6f} |")
        sections.append("")

        sections.append(f"### {breakdown_label} Breakdown")
        sections.append("")
        sections.append(
            f"| {breakdown_label} | Treatment | Runs | Success | Failure | Timeout | Error | Success Rate | "
            "Avg Progress | Tokens | Est. Cost (USD) | Default Decision Rate |"
        )
        sections.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for group, row in model_summary.items():
            cost = "n/a" if row["cost"] is None else f"{row['cost']:.6f}"
            sections.append(
                f"| {group} | `{row['treatment_signature']}` | {row['runs']} | {row['success']} | {row['failure']} | "
                f"{row['timeout']} | {row['error']} | {row['success_rate']:.1f}% | {row['avg_progress']:.1f}% | "
                f"{row['tokens']} | {cost} | {row['default_rate']:.1f}% |"
            )
        sections.append("")

        if failure_rows:
            sections.append("### Failure Highlights")
            sections.append("")
            for row in failure_rows:
                agent_label = _group_label(row.model, row.harness, harnesses_by_model)
                sections.append(
                    f"- run `{row.run_id}` | agent `{agent_label}` | quest `{row.quest_name}` | outcome `{row.outcome}`"
                )
                if row.selected_choice:
                    sections.append(f"  selected: {row.selected_choice}")
                if row.selected_reasoning:
                    sections.append(f"  reasoning: {row.selected_reasoning}")
                if row.selected_observation:
                    sections.append(f"  observation: {row.selected_observation}")
                if row.summary_path:
                    sections.append(f"  summary: `{row.summary_path}`")
            sections.append("")

    if len(selected_ids) > 1 and all_insights:
        summary = _format_benchmark_summary(all_insights)
        sections.append("## Combined Overview")
        sections.append("")
        sections.append("| Metric | Value |")
        sections.append("|---|---:|")
        sections.append(f"| Benchmarks | {len(selected_ids)} |")
        sections.append(f"| Total runs | {summary['total']} |")
        sections.append(f"| Success rate | {summary['success_rate']:.1f}% |")
        sections.append(f"| Total tokens | {summary['total_tokens']} |")
        if summary["total_cost"] is None:
            sections.append("| Estimated cost (USD) | n/a |")
        else:
            sections.append(f"| Estimated cost (USD) | {summary['total_cost']:.6f} |")
        sections.append("")

    return "\n".join(sections).strip() + "\n", selected_ids
