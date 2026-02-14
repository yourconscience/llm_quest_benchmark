"""Markdown report generator for benchmark runs."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class RunInsight:
    """Parsed and enriched benchmark run data."""

    benchmark_id: str
    run_id: int
    model: str
    quest_name: str
    outcome: str
    duration: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: Optional[float]
    priced_steps: int
    decision_steps: int
    default_decision_steps: int
    selected_choice: Optional[str]
    selected_reasoning: Optional[str]
    selected_analysis: Optional[str]
    selected_observation: Optional[str]
    summary_path: Optional[Path]


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _shorten(text: Optional[str], limit: int = 180) -> Optional[str]:
    if not text:
        return text
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3] + "..."


def _extract_model(run_row: Dict[str, Any]) -> str:
    model = None
    raw_cfg = run_row.get("agent_config")
    if isinstance(raw_cfg, dict):
        model = raw_cfg.get("model")
    elif isinstance(raw_cfg, str):
        try:
            model = json.loads(raw_cfg).get("model")
        except json.JSONDecodeError:
            model = None
    if model:
        return str(model)

    agent_id = str(run_row.get("agent_id") or "")
    if agent_id.startswith("llm_"):
        return agent_id[len("llm_") :]
    return agent_id or "unknown"


def _extract_last_decision(steps: List[Dict[str, Any]]) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], int, int]:
    decision_steps = 0
    default_decisions = 0
    last_choice = None
    last_reasoning = None
    last_analysis = None
    last_observation = None

    for step in steps:
        if not isinstance(step, dict):
            continue
        choices = step.get("choices")
        if not isinstance(choices, dict) or len(choices) <= 1:
            continue
        decision_steps += 1
        llm_decision = step.get("llm_decision") if isinstance(step.get("llm_decision"), dict) else {}
        if bool(llm_decision.get("is_default", False)):
            default_decisions += 1

        choice_map = llm_decision.get("choice")
        selected = None
        if isinstance(choice_map, dict) and choice_map:
            idx, text = next(iter(choice_map.items()))
            selected = f"{idx}: {text}"

        last_choice = selected
        last_reasoning = _shorten(llm_decision.get("reasoning"))
        last_analysis = _shorten(llm_decision.get("analysis"))
        last_observation = _shorten(step.get("observation"), 220)

    return (
        last_choice,
        last_reasoning,
        last_analysis,
        last_observation,
        decision_steps,
        default_decisions,
    )


def _resolve_run_summary_path(run_row: Dict[str, Any]) -> Optional[Path]:
    run_id = run_row.get("id")
    quest_name = run_row.get("quest_name")
    agent_id = run_row.get("agent_id")
    if run_id is None or not quest_name or not agent_id:
        return None
    return Path("results") / str(agent_id) / str(quest_name) / f"run_{run_id}" / "run_summary.json"


def _parse_run_insight(benchmark_id: str, run_row: Dict[str, Any]) -> RunInsight:
    summary_path = _resolve_run_summary_path(run_row)
    run_summary = _load_json(summary_path) if summary_path else None

    run_id = int(run_row.get("id") or -1)
    outcome = str(run_row.get("outcome") or "UNKNOWN")
    duration = float(run_row.get("run_duration") or 0.0)
    usage = {}
    steps: List[Dict[str, Any]] = []

    if isinstance(run_summary, dict):
        outcome = str(run_summary.get("outcome") or outcome)
        duration = float(run_summary.get("run_duration") or duration or 0.0)
        usage = run_summary.get("usage") if isinstance(run_summary.get("usage"), dict) else {}
        loaded_steps = run_summary.get("steps")
        if isinstance(loaded_steps, list):
            steps = [s for s in loaded_steps if isinstance(s, dict)]

    selected_choice, selected_reasoning, selected_analysis, selected_observation, decision_steps, default_decisions = _extract_last_decision(steps)

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


def _latest_benchmark_ids(output_dir: Path, limit: int = 1) -> List[str]:
    if not output_dir.exists():
        return []
    benchmark_dirs = [p for p in output_dir.iterdir() if p.is_dir()]
    benchmark_dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return [p.name for p in benchmark_dirs[:limit]]


def _collect_insights(benchmark_id: str, output_dir: Path) -> List[RunInsight]:
    summary_path = output_dir / benchmark_id / "benchmark_summary.json"
    benchmark_summary = _load_json(summary_path)
    if not benchmark_summary:
        return []
    db_runs = benchmark_summary.get("db_runs") if isinstance(benchmark_summary.get("db_runs"), list) else []
    return [_parse_run_insight(benchmark_id, row) for row in db_runs if isinstance(row, dict)]


def _format_benchmark_summary(insights: List[RunInsight]) -> Dict[str, Any]:
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


def _format_model_summary(insights: List[RunInsight]) -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, List[RunInsight]] = defaultdict(list)
    for insight in insights:
        grouped[insight.model].append(insight)

    model_summary: Dict[str, Dict[str, Any]] = {}
    for model, rows in sorted(grouped.items()):
        outcomes = Counter(r.outcome for r in rows)
        total = len(rows)
        success = outcomes.get("SUCCESS", 0)
        total_tokens = sum(r.total_tokens for r in rows)
        total_cost = sum((r.estimated_cost_usd or 0.0) for r in rows)
        priced_runs = sum(1 for r in rows if r.estimated_cost_usd is not None)
        decision_steps = sum(r.decision_steps for r in rows)
        default_steps = sum(r.default_decision_steps for r in rows)
        model_summary[model] = {
            "runs": total,
            "success": success,
            "failure": outcomes.get("FAILURE", 0),
            "timeout": outcomes.get("TIMEOUT", 0),
            "error": outcomes.get("ERROR", 0),
            "success_rate": (success / total * 100.0) if total else 0.0,
            "tokens": total_tokens,
            "cost": total_cost if priced_runs else None,
            "default_rate": (default_steps / decision_steps * 100.0) if decision_steps else 0.0,
        }
    return model_summary


def _format_failure_rows(insights: List[RunInsight], limit: int = 12) -> List[RunInsight]:
    failed = [i for i in insights if i.outcome in {"FAILURE", "TIMEOUT", "ERROR"}]
    failed.sort(key=lambda row: (row.outcome, row.model, row.quest_name, row.run_id))
    return failed[:limit]


def render_benchmark_report(
    benchmark_ids: Optional[List[str]] = None,
    output_dir: str = "results/benchmarks",
) -> Tuple[str, List[str]]:
    """Render markdown report for one or multiple benchmark IDs."""
    output_root = Path(output_dir)
    selected_ids = benchmark_ids or _latest_benchmark_ids(output_root, limit=1)
    selected_ids = [b for b in selected_ids if b]
    if not selected_ids:
        raise ValueError(f"No benchmark directories found under {output_root}")

    sections: List[str] = []
    sections.append("# Benchmark Report")
    sections.append("")
    sections.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    sections.append("")

    all_insights: List[RunInsight] = []
    for benchmark_id in selected_ids:
        insights = _collect_insights(benchmark_id, output_root)
        if not insights:
            sections.append(f"## {benchmark_id}")
            sections.append("")
            sections.append("No benchmark data found.")
            sections.append("")
            continue

        all_insights.extend(insights)
        summary = _format_benchmark_summary(insights)
        model_summary = _format_model_summary(insights)
        failure_rows = _format_failure_rows(insights)

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

        sections.append("### Model Breakdown")
        sections.append("")
        sections.append("| Model | Runs | Success | Failure | Timeout | Error | Success Rate | Tokens | Est. Cost (USD) | Default Decision Rate |")
        sections.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
        for model, row in model_summary.items():
            cost = "n/a" if row["cost"] is None else f"{row['cost']:.6f}"
            sections.append(
                f"| {model} | {row['runs']} | {row['success']} | {row['failure']} | {row['timeout']} | "
                f"{row['error']} | {row['success_rate']:.1f}% | {row['tokens']} | {cost} | {row['default_rate']:.1f}% |"
            )
        sections.append("")

        if failure_rows:
            sections.append("### Failure Highlights")
            sections.append("")
            for row in failure_rows:
                sections.append(
                    f"- run `{row.run_id}` | model `{row.model}` | quest `{row.quest_name}` | outcome `{row.outcome}`"
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
