"""Tests for benchmark result summary grouping (calculate_summary_stats, print_summary)."""

from llm_quest_benchmark.executors.benchmark import calculate_summary_stats, print_summary


def _result(model, harness, outcome, agent_id=None):
    return {
        "quest": "quests/Boat.qm",
        "model": model,
        "temperature": 0.4,
        "harness": harness,
        "template": "reasoning.jinja",
        "memory_mode": "default",
        "agent_id": agent_id or f"llm_{model}_{harness}",
        "attempt": 1,
        "outcome": outcome,
        "reward": 1.0 if outcome == "SUCCESS" else 0.0,
        "error": None,
    }


def test_calculate_summary_stats_keeps_single_model_single_harness_key_unchanged():
    """Backward compatibility: with one harness per model, the group key stays the bare model name."""
    results = [
        _result("gpt-5-mini", "reasoning_recent", "SUCCESS"),
        _result("gpt-5-mini", "reasoning_recent", "FAILURE"),
    ]

    summary = calculate_summary_stats(results)

    assert set(summary["models"].keys()) == {"gpt-5-mini"}
    assert summary["models"]["gpt-5-mini"]["total_runs"] == 2
    assert summary["models"]["gpt-5-mini"]["success"] == 1


def test_calculate_summary_stats_splits_same_model_different_harness():
    """Two harnesses sharing a model must not collapse into one aggregate row."""
    results = [
        _result("gemini-3-flash", "reasoning_recent", "SUCCESS"),
        _result("gemini-3-flash", "reasoning_recent", "SUCCESS"),
        _result("gemini-3-flash", "programmatic_memory", "FAILURE"),
        _result("gemini-3-flash", "programmatic_memory", "FAILURE"),
        _result("gemini-3-flash", "programmatic_memory", "FAILURE"),
    ]

    summary = calculate_summary_stats(results)

    assert set(summary["models"].keys()) == {
        "gemini-3-flash [reasoning_recent]",
        "gemini-3-flash [programmatic_memory]",
    }
    recent = summary["models"]["gemini-3-flash [reasoning_recent]"]
    programmatic = summary["models"]["gemini-3-flash [programmatic_memory]"]
    assert recent["total_runs"] == 2
    assert recent["success"] == 2
    assert programmatic["total_runs"] == 3
    assert programmatic["failed"] == 3
    # Overall totals stay correct even though the runs are split across groups.
    assert summary["total_runs"] == 5
    assert summary["total_success"] == 2
    assert summary["total_failures"] == 3


def test_calculate_summary_stats_keeps_human_and_random_choice_labels_bare():
    results = [
        _result("human", "human", "SUCCESS"),
        _result("random_policy", "random_choice", "FAILURE"),
    ]

    summary = calculate_summary_stats(results)

    assert set(summary["models"].keys()) == {"human", "random_policy"}


def test_print_summary_reports_each_harness_separately(capsys):
    results = [
        _result("gemini-3-flash", "reasoning_recent", "SUCCESS"),
        _result("gemini-3-flash", "programmatic_memory", "FAILURE"),
    ]

    print_summary(results)

    out = capsys.readouterr().out
    assert "Agent: gemini-3-flash [reasoning_recent]" in out
    assert "Agent: gemini-3-flash [programmatic_memory]" in out
