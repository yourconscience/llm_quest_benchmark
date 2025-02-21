"""Quest run analyzer for metrics analysis"""
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

from llm_quest_benchmark.core.logging import LogManager
from llm_quest_benchmark.utils.choice_mapper import ChoiceMapper
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.renderers.benchmark_result import BenchmarkResultRenderer

# Initialize logging
log_manager = LogManager()
log = log_manager.get_logger()

def find_latest_metrics_file() -> Optional[Path]:
    """Find the most recent metrics file in the metrics directory"""
    metrics_dir = Path("metrics")
    if not metrics_dir.exists():
        return None

    files = list(metrics_dir.glob("quest_run_*.jsonl"))
    if not files:
        return None

    # Sort by modification time in descending order
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0]

def analyze_quest_run(
    metrics_file: Optional[Path] = None,
    debug: bool = False,
) -> Dict[str, Any]:
    """Analyze metrics from a quest run.

    Args:
        metrics_file: Path to the metrics JSON file. If not provided, uses most recent file.
        debug: Enable debug logging and output.

    Returns:
        Dict containing analysis results

    Raises:
        ValueError: If metrics file is not found or invalid
    """
    log_manager.setup(debug)

    # If no file provided, use most recent
    if metrics_file is None:
        metrics_file = find_latest_metrics_file()
        if metrics_file is None:
            raise ValueError("No metrics files found")
        log.info(f"Using metrics file: {metrics_file}")

    if not metrics_file.exists():
        raise ValueError(f"Metrics file not found: {metrics_file}")

    try:
        # Read and parse JSONL file
        steps = []
        with open(str(metrics_file), "r", encoding='utf-8') as f:
            for line in f:
                steps.append(json.loads(line))

        if not steps:
            raise ValueError("No steps found in metrics file")

        # Calculate summary
        total_steps = len(steps)
        final_reward = steps[-1]["reward"]  # Only care about final reward
        quest_file = steps[0].get("quest_file", "unknown")
        is_llm = steps[0].get("is_llm", False)
        model = steps[0].get("model", "unknown")
        template = steps[0].get("template", "unknown")

        # Determine quest outcome
        outcome = "SUCCESS" if final_reward > 0 else "FAILURE"

        # Prepare analysis results
        results = {
            "summary": {
                "quest_file": quest_file,
                "player_type": "LLM Agent" if is_llm else "Human Player",
                "model": model if is_llm else None,
                "template": template if is_llm else None,
                "total_steps": total_steps,
                "outcome": outcome,
            },
            "steps": []
        }

        # Process steps, skipping single-choice steps
        for i, step in enumerate(steps, 1):
            choices = step['choices']
            if len(choices) <= 1:
                continue  # Skip steps with 0 or 1 choices

            # Use ChoiceMapper to map choice numbers
            mapper = ChoiceMapper(choices)
            try:
                # Convert response to int since we expect sequential numbers from LLM
                choice_num = int(step['response'])
                mapped_action = mapper.get_jump_id(choice_num)
            except (ValueError, TypeError):
                # If conversion fails, use original response (might be direct jump ID)
                mapped_action = step['response']

            step_info = {
                "step": i,
                "action": mapped_action,
                "state": step['state'],  # Include full state without truncation
                "choices": choices,
            }

            # Include LLM response details if available
            if step.get('llm_response'):
                step_info['llm_response'] = step['llm_response']
            if step.get('reasoning'):
                step_info['reasoning'] = step['reasoning']
            if step.get('analysis'):
                step_info['analysis'] = step['analysis']

            results["steps"].append(step_info)

        return results

    except Exception as e:
        log.exception(f"Error analyzing metrics: {e}")
        raise ValueError(f"Error analyzing metrics: {e}")


def find_latest_benchmark_file() -> Optional[Path]:
    """Find the most recent benchmark file in the metrics/benchmarks directory"""
    metrics_dir = Path("metrics/benchmarks")
    if not metrics_dir.exists():
        return None

    files = list(metrics_dir.glob("benchmark_*.json"))
    if not files:
        return None

    # Sort by modification time in descending order
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0]


def analyze_benchmark(
    benchmark_file: Optional[Path] = None,
    quest_filter: Optional[str] = None,
    debug: bool = False,
) -> Dict[str, Any]:
    """Analyze metrics from a benchmark run.

    Args:
        benchmark_file: Path to the benchmark JSON file. If not provided, uses most recent file.
        quest_filter: Optional quest name to filter results (e.g. 'boat.qm')
        debug: Enable debug logging and output.

    Returns:
        Dict containing analysis results

    Raises:
        ValueError: If benchmark file is not found or invalid
    """
    log_manager.setup(debug)

    # If no file provided, use most recent
    if benchmark_file is None:
        benchmark_file = find_latest_benchmark_file()
        if benchmark_file is None:
            raise ValueError("No benchmark files found")
        log.info(f"Using benchmark file: {benchmark_file}")

    if not benchmark_file.exists():
        raise ValueError(f"Benchmark file not found: {benchmark_file}")

    try:
        # Read and parse JSON file
        with open(str(benchmark_file), "r", encoding='utf-8') as f:
            benchmark_data = json.load(f)

        # Filter quests if requested
        if quest_filter:
            filtered_quests = []
            for quest in benchmark_data['quests']:
                if quest['name'] == quest_filter or quest['name'] == Path(quest_filter).stem:
                    filtered_quests.append(quest)
            if not filtered_quests:
                raise ValueError(f"No results found for quest: {quest_filter}")
            benchmark_data['quests'] = filtered_quests
            # Update summary stats for filtered quests
            benchmark_data['summary']['total_quests'] = len(filtered_quests)
            benchmark_data['summary']['total_runs'] = sum(q['total_runs'] for q in filtered_quests)
            benchmark_data['summary']['outcomes'] = {}
            for quest in filtered_quests:
                for outcome, count in quest['outcomes'].items():
                    if outcome not in benchmark_data['summary']['outcomes']:
                        benchmark_data['summary']['outcomes'][outcome] = 0
                    benchmark_data['summary']['outcomes'][outcome] += count

        # Create renderer and display results
        renderer = BenchmarkResultRenderer(debug=debug)
        renderer.render_benchmark_results(benchmark_data, debug=debug or quest_filter is not None)

        return benchmark_data

    except Exception as e:
        log.exception(f"Error analyzing benchmark: {e}")
        raise ValueError(f"Error analyzing benchmark: {e}")