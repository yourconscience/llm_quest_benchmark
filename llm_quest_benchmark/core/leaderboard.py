"""Leaderboard JSON generator for benchmark runs."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import glob
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from llm_quest_benchmark.llm.client import parse_model_name

TEMPLATE_TO_MODE = {
    "stub": ("stub", "Baseline (A)"),
    "reasoning": ("reasoning", "Prompted (B)"),
    "strategic": ("reasoning", "Prompted (B)"),
    "light_hints": ("light_hints", "Knowledge (C)"),
    "planner": ("planner", "Planner (D)"),
    "tool_augmented": ("tool_augmented", "Tool-aug (E)"),
}

MODE_ORDER = ["stub", "reasoning", "light_hints", "planner", "tool_augmented"]


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _strip_template_suffix(template_name: str) -> str:
    return Path(template_name or "").stem


def _mode_from_template(template_name: str) -> Tuple[str, str]:
    template_id = _strip_template_suffix(template_name)
    return TEMPLATE_TO_MODE.get(template_id, (template_id or "unknown", template_id or "unknown"))


def _combine_numeric_tokens(parts: List[str]) -> List[str]:
    combined: List[str] = []
    i = 0
    while i < len(parts):
        current = parts[i]
        if current.isdigit() and i + 1 < len(parts) and parts[i + 1].isdigit():
            combined.append(f"{current}.{parts[i + 1]}")
            i += 2
            continue
        combined.append(current)
        i += 1
    return combined


def _model_label(model_id: str) -> str:
    parts = [part for part in model_id.split("-") if part]
    if parts and parts[-1].lower() == "chat":
        parts = parts[:-1]
    parts = _combine_numeric_tokens(parts)
    if len(parts) >= 2 and parts[0].lower() == "gpt":
        return " ".join([f"GPT-{parts[1]}"] + [part.title() for part in parts[2:]])

    normalized: List[str] = []
    for part in parts:
        lowered = part.lower()
        if lowered == "gpt":
            normalized.append("GPT")
        elif lowered == "deepseek":
            normalized.append("DeepSeek")
        elif lowered == "claude":
            normalized.append("Claude")
        elif lowered == "gemini":
            normalized.append("Gemini")
        else:
            normalized.append(part if any(ch.isdigit() for ch in part) else part.title())
    return " ".join(normalized)


def _quest_id_from_path(quest_path: str) -> str:
    if quest_path:
        return Path(str(quest_path)).stem
    return "unknown"


def _detect_quest_lang(quest_path: str) -> str:
    if not quest_path:
        return "EN"
    p = Path(quest_path)
    if "_ru" in p.stem.lower():
        return "RU"
    for part in p.parts[:-1]:
        lowered = part.lower()
        if lowered == "ru" or lowered.endswith("_ru"):
            return "RU"
    return "EN"


def _mean(values: Iterable[float]) -> float:
    materialized = list(values)
    if not materialized:
        return 0.0
    return sum(materialized) / len(materialized)


def _resolve_benchmark_dirs(benchmark_dirs: List[str]) -> List[Path]:
    resolved: List[Path] = []
    seen: set[str] = set()

    for raw in benchmark_dirs:
        matches = [Path(match) for match in glob.glob(raw)] if glob.has_magic(raw) else [Path(raw)]
        for match in matches:
            candidates: List[Path]
            if match.is_file() and match.name == "benchmark_summary.json":
                candidates = [match.parent]
            elif match.is_dir() and (match / "benchmark_summary.json").exists():
                candidates = [match]
            elif match.is_dir():
                candidates = sorted(
                    path
                    for path in match.iterdir()
                    if path.is_dir() and (path / "benchmark_summary.json").exists()
                )
            else:
                candidates = []

            for candidate in candidates:
                key = str(candidate.resolve())
                if key in seen:
                    continue
                seen.add(key)
                resolved.append(candidate)

    if not resolved:
        raise FileNotFoundError(f"No benchmark directories found for: {benchmark_dirs}")
    return sorted(resolved)


def generate_leaderboard(benchmark_dirs: List[str], output_path: str) -> Dict[str, Any]:
    resolved_dirs = _resolve_benchmark_dirs(benchmark_dirs)

    grouped_rows: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    model_entries: Dict[str, Dict[str, str]] = {}
    mode_entries: Dict[str, Dict[str, str]] = {}
    quest_entries: Dict[str, Dict[str, str]] = {}
    benchmark_ids: List[str] = []

    for benchmark_dir in resolved_dirs:
        summary = _load_json(benchmark_dir / "benchmark_summary.json")
        if not summary:
            continue

        benchmark_id = summary.get("benchmark_id")
        if benchmark_id:
            benchmark_ids.append(str(benchmark_id))

        results_list = summary.get("results") if isinstance(summary.get("results"), list) else []
        db_runs = summary.get("db_runs") if isinstance(summary.get("db_runs"), list) else []

        for i, result_row in enumerate(results_list):
            if not isinstance(result_row, dict):
                continue

            model = str(result_row.get("model") or "unknown")
            template = str(result_row.get("template") or "")
            mode_id, mode_label = _mode_from_template(template)
            quest_path = str(result_row.get("quest") or "")
            quest_id = _quest_id_from_path(quest_path)
            quest_lang = _detect_quest_lang(quest_path)
            outcome = str(result_row.get("outcome") or "UNKNOWN")

            # Correlate with db_runs by index to get run ID for metrics
            usage: Dict[str, Any] = {}
            metrics: Dict[str, Any] = {}
            if i < len(db_runs) and isinstance(db_runs[i], dict):
                db_run = db_runs[i]
                run_id = db_run.get("id")
                quest_name = db_run.get("quest_name")
                agent_id = db_run.get("agent_id")
                if run_id is not None and quest_name and agent_id:
                    run_path = Path("results") / str(agent_id) / str(quest_name) / f"run_{run_id}" / "run_summary.json"
                    run_summary = _load_json(run_path) or {}
                    usage = run_summary.get("usage") if isinstance(run_summary.get("usage"), dict) else {}
                    metrics = run_summary.get("metrics") if isinstance(run_summary.get("metrics"), dict) else {}

            try:
                spec = parse_model_name(model)
                provider = spec.provider
                label_source = spec.model_id
                if provider == "openrouter" and "/" in label_source:
                    provider = label_source.split("/", 1)[0]
                    label_source = label_source.split("/", 1)[1]
            except Exception:
                provider = "unknown"
                label_source = model
            display_id = label_source if model.startswith("openrouter:") else model

            grouped_rows[(display_id, mode_id, quest_id)].append(
                {
                    "outcome": outcome,
                    "total_steps": float(metrics.get("total_steps") or 0),
                    "total_tokens": float(usage.get("total_tokens") or 0),
                    "estimated_cost_usd": float(usage.get("estimated_cost_usd") or 0),
                    "repetition_rate": float(metrics.get("repetition_rate") or 0),
                }
            )
            model_entries[display_id] = {
                "id": display_id,
                "provider": provider,
                "label": _model_label(label_source),
            }
            mode_entries[mode_id] = {"id": mode_id, "label": mode_label}
            quest_entries[quest_id] = {"id": quest_id, "lang": quest_lang}

    agg_results = []
    for (model, mode_id, quest_id), rows in sorted(grouped_rows.items()):
        run_count = len(rows)
        success_count = sum(1 for row in rows if row["outcome"] == "SUCCESS")
        agg_results.append(
            {
                "model": model,
                "mode": mode_id,
                "quest": quest_id,
                "runs": run_count,
                "success_rate": (success_count / run_count) if run_count else 0.0,
                "avg_steps": _mean(row["total_steps"] for row in rows),
                "avg_tokens": _mean(row["total_tokens"] for row in rows),
                "avg_cost_usd": _mean(row["estimated_cost_usd"] for row in rows),
                "repetition_rate": _mean(row["repetition_rate"] for row in rows),
            }
        )

    mode_rank = {mode_id: index for index, mode_id in enumerate(MODE_ORDER)}
    leaderboard = {
        "generated": datetime.now().isoformat(),
        "benchmark_id": benchmark_ids[0] if len(set(benchmark_ids)) == 1 and benchmark_ids else "combined",
        "models": sorted(model_entries.values(), key=lambda item: item["id"]),
        "modes": sorted(mode_entries.values(), key=lambda item: (mode_rank.get(item["id"], 999), item["id"])),
        "quests": sorted(quest_entries.values(), key=lambda item: item["id"]),
        "results": sorted(
            agg_results,
            key=lambda item: (item["model"], mode_rank.get(item["mode"], 999), item["mode"], item["quest"]),
        ),
    }

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(leaderboard, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return leaderboard
