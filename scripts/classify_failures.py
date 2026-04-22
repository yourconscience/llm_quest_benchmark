#!/usr/bin/env python3
"""Classify failure modes in quest runs using Claude as LLM judge.

Reads the analysis manifest, pipes condensed traces to `claude -p`,
collects structured failure classifications.

Usage:
    uv run scripts/classify_failures.py [--manifest research/analysis_manifest.json] [--output research/failure_classifications.json] [--workers 5] [--model haiku]
"""

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

CLASSIFICATION_PROMPT = """You are an expert at analyzing LLM agent failures in interactive fiction quests.

Below is a condensed trace of an LLM agent playing a text-based quest. The agent failed.
Analyze WHY it failed and classify the failure mode.

FAILURE MODES:
- LOOP: Agent gets stuck repeating the same actions. Revisits locations or choices cyclically. The most common failure.
- BAD_STRATEGY: Agent makes poor strategic decisions despite understanding the quest. Chooses suboptimal paths, wastes resources, or ignores clues.
- COMPREHENSION: Agent misunderstands the quest text, misreads choices, or picks options that don't match its stated reasoning.
- DEAD_END: Agent reaches an unwinnable state due to earlier irreversible decisions. The quest becomes impossible to complete.
- PARSE_FAIL: Agent's response couldn't be parsed correctly, defaulting to a random/first choice repeatedly.

Respond with ONLY a JSON object, no other text:
{
  "failure_mode": "LOOP|BAD_STRATEGY|COMPREHENSION|DEAD_END|PARSE_FAIL",
  "severity": 1-3,
  "first_problem_step": <step number where the failure pattern first appears>,
  "reason": "<one sentence explaining the failure>"
}

Severity scale:
1 = Minor: agent made progress but failed at the end
2 = Moderate: agent struggled from early on, partial progress
3 = Critical: agent never made meaningful progress, stuck immediately

TRACE:
"""


def condense_trace(run: dict) -> str:
    """Extract key info from a run, keeping it under ~3000 tokens."""
    lines = []
    lines.append(f"Quest: {run.get('quest_name', 'unknown')}")
    lines.append(f"Agent: {run.get('agent_id', 'unknown')}")
    lines.append(f"Outcome: {run.get('outcome', 'unknown')}")
    lines.append(f"Total steps: {len(run.get('steps', []))}")
    lines.append(f"Reward: {run.get('reward', 0)}")
    lines.append("")

    steps = run.get("steps", [])
    # For long traces, show first 5, last 5, and sample middle
    if len(steps) <= 15:
        show_steps = steps
    else:
        middle_idx = len(steps) // 2
        show_steps = steps[:5] + [{"_marker": f"... ({len(steps) - 10} steps omitted) ..."}] + steps[middle_idx - 1 : middle_idx + 2] + [{"_marker": "..."}] + steps[-5:]

    for s in show_steps:
        if "_marker" in s:
            lines.append(s["_marker"])
            continue

        step_num = s.get("step", "?")
        obs = (s.get("observation") or "")[:200]
        choices = s.get("choices", {})
        decision = s.get("llm_decision", {})
        chosen = decision.get("choice", {})
        reasoning = (decision.get("reasoning") or decision.get("analysis") or "")[:150]
        parse_mode = decision.get("parse_mode", "")

        lines.append(f"Step {step_num}:")
        lines.append(f"  Observation: {obs}")
        if choices:
            choice_str = " | ".join(f"{k}: {v[:60]}" for k, v in list(choices.items())[:6])
            lines.append(f"  Choices: {choice_str}")
        if chosen:
            chosen_str = " | ".join(f"{k}: {v[:60]}" for k, v in chosen.items())
            lines.append(f"  Chose: {chosen_str}")
        if reasoning:
            lines.append(f"  Reasoning: {reasoning}")
        if parse_mode and parse_mode != "json_parsed":
            lines.append(f"  Parse mode: {parse_mode}")
        lines.append("")

    # Track action repetitions
    actions = []
    for s in steps:
        choice = s.get("llm_decision", {}).get("choice", {})
        action_key = str(sorted(choice.items())) if choice else "?"
        actions.append(action_key)

    if len(actions) > 5:
        from collections import Counter
        action_counts = Counter(actions)
        most_common = action_counts.most_common(3)
        rep_str = ", ".join(f"'{a[:40]}' x{c}" for a, c in most_common)
        lines.append(f"Action repetition: {rep_str}")
        unique_ratio = len(set(actions)) / len(actions)
        lines.append(f"Unique actions: {len(set(actions))}/{len(actions)} ({unique_ratio:.1%})")

    return "\n".join(lines)


def classify_run(run_path: str, model: str) -> dict:
    """Classify a single run using claude -p."""
    try:
        run = json.loads(Path(run_path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return {"path": run_path, "error": str(e)}

    trace = condense_trace(run)
    prompt = CLASSIFICATION_PROMPT + trace

    try:
        result = subprocess.run(
            ["claude", "-p", "--model", model, "--output-format", "text"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=120,
        )
        response = result.stdout.strip()

        # Try to parse JSON from response
        # Handle cases where claude wraps in markdown code blocks
        if "```" in response:
            lines = response.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_block = not in_block
                    continue
                if in_block:
                    json_lines.append(line)
            response = "\n".join(json_lines)

        # Find JSON object in response
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            classification = json.loads(response[start:end])
        else:
            classification = {"failure_mode": "UNKNOWN", "reason": f"Could not parse: {response[:200]}"}

        return {
            "path": run_path,
            "quest": run.get("quest_name"),
            "agent": run.get("agent_id"),
            "outcome": run.get("outcome"),
            "steps": len(run.get("steps", [])),
            **classification,
        }
    except subprocess.TimeoutExpired:
        return {"path": run_path, "error": "timeout"}
    except Exception as e:
        return {"path": run_path, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="research/analysis_manifest.json")
    parser.add_argument("--output", default="research/failure_classifications.json")
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--model", default="haiku", help="Claude model for classification")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of runs (0 = all)")
    args = parser.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    runs = manifest["runs"]
    if args.limit > 0:
        runs = runs[: args.limit]

    print(f"Classifying {len(runs)} runs with {args.workers} workers using claude -p ({args.model})")

    results = []
    errors = 0
    completed = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(classify_run, r["path"], args.model): r for r in runs}
        for future in as_completed(futures):
            completed += 1
            result = future.result()
            if "error" in result:
                errors += 1
                if errors <= 5:
                    print(f"  ERROR [{completed}/{len(runs)}]: {result.get('path', '?')}: {result['error']}")
            else:
                fm = result.get("failure_mode", "?")
                quest = result.get("quest", "?")
                if completed % 25 == 0 or completed <= 5:
                    print(f"  [{completed}/{len(runs)}] {quest}: {fm} - {result.get('reason', '')[:60]}")
            results.append(result)

    # Sort by quest then agent for readability
    results.sort(key=lambda r: (r.get("quest", ""), r.get("agent", "")))

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "total_classified": len(results),
        "errors": errors,
        "model": args.model,
        "classifications": results,
    }
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nDone: {len(results)} classified ({errors} errors)")
    print(f"Written to {output_path}")

    # Print summary
    from collections import Counter
    modes = Counter(r.get("failure_mode") for r in results if "error" not in r)
    print("\nFailure mode distribution:")
    for mode, count in modes.most_common():
        print(f"  {mode}: {count} ({100 * count / max(1, len(results) - errors):.1f}%)")


if __name__ == "__main__":
    main()
