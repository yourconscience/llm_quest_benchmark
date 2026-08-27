"""End-to-end tests for benchmark functionality"""

import logging
import time

import pytest

from llm_quest_benchmark.constants import SYSTEM_ROLE_TEMPLATE
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.executors import benchmark as benchmark_module
from llm_quest_benchmark.executors.benchmark import run_benchmark
from llm_quest_benchmark.schemas.config import BenchmarkConfig, HarnessConfig


def _fake_task_for_parallel_test(task, result_queue):
    time.sleep(0.4)
    result_queue.put(
        {
            "event": "done",
            "run_index": task["run_index"],
            "result": benchmark_module._result_entry(
                task["quest"],
                task["agent_config"],
                task["attempt"],
                QuestOutcome.FAILURE.name,
            ),
        }
    )


def _slow_task_for_timeout_test(task, result_queue):
    time.sleep(5)


def _task_reporting_max_steps_seen(task, result_queue):
    """Module-level (spawn-picklable) fake task: reports what task['max_steps']
    it received back through the result, instead of doing real quest work."""
    result = benchmark_module._result_entry(
        task["quest"], task["agent_config"], task["attempt"], QuestOutcome.FAILURE.name
    )
    result["max_steps_seen"] = task.get("max_steps")
    result_queue.put({"event": "done", "run_index": task["run_index"], "result": result})


@pytest.mark.timeout(20)  # 20 seconds timeout for benchmark test
def test_benchmark_e2e(caplog, tmp_path):
    """Test end-to-end benchmark functionality."""
    caplog.set_level(logging.DEBUG)  # Show all logs in test output

    # Create a test quest file
    quest_path = tmp_path / "test_quest.qm"
    quest_path.write_text("""
    [start]
    text: You are in a room.
    choices:
        - Go north: room1
        - Go south: room2

    [room1]
    text: You found the treasure!
    success: true

    [room2]
    text: Dead end.
    failure: true
    """)

    config = BenchmarkConfig(
        quests=[str(quest_path)],
        agents=[
            HarnessConfig(
                model="random_choice",  # Use random_choice for testing
                harness="random_choice",
                system_template=SYSTEM_ROLE_TEMPLATE,
                temperature=0.0,
                skip_single=True,
            )
        ],
        quest_timeout=5,
        max_workers=1,
        debug=True,
        output_dir=str(tmp_path),
    )

    try:
        # Run benchmark
        results = run_benchmark(config)

        # Verify results
        assert len(results) > 0, "No results returned"
        assert len(results) == len(config.agents), f"Expected {len(config.agents)} results, got {len(results)}"

        # Check first result
        result = results[0]
        assert result["quest"] == str(quest_path)
        assert result["model"] == "random_policy"
        assert result["temperature"] == 0.0
        assert result["harness"] == "random_choice"
        assert result["treatment"]["loop"] == "random"
        assert result["treatment_signature"].startswith("t2_")
        assert result["attempt"] == 1
        assert "agent_id" in result
        assert "outcome" in result

        # Check benchmark artifact files were created.
        benchmark_dir = tmp_path / config.benchmark_id
        assert (benchmark_dir / "benchmark_config.json").exists(), "Missing benchmark config artifact"
        assert (benchmark_dir / "benchmark_summary.json").exists(), "Missing benchmark summary artifact"

    except Exception as e:
        print(f"\nBenchmark failed with error: {str(e)}")
        raise e


@pytest.mark.timeout(20)
def test_benchmark_supports_multiple_runs_per_agent(tmp_path):
    quest_path = tmp_path / "repeatable_quest.qm"
    quest_path.write_text("""
    [start]
    text: You are in a room.
    choices:
        - Go north: room1
        - Go south: room2

    [room1]
    text: You found the treasure!
    success: true

    [room2]
    text: Dead end.
    failure: true
    """)

    config = BenchmarkConfig(
        quests=[str(quest_path)],
        agents=[
            HarnessConfig(
                model="random_choice",
                harness="random_choice",
                temperature=0.0,
                runs=2,
                skip_single=True,
            )
        ],
        quest_timeout=5,
        max_workers=1,
        output_dir=str(tmp_path),
    )

    results = run_benchmark(config)

    assert len(results) == 2
    assert [result["attempt"] for result in results] == [1, 2]


@pytest.mark.timeout(10)
def test_benchmark_uses_max_workers(monkeypatch, tmp_path):
    quest_path = tmp_path / "parallel_quest.qm"
    quest_path.write_text("""
    [start]
    text: Done.
    failure: true
    """)

    monkeypatch.setattr(benchmark_module, "_run_benchmark_task", _fake_task_for_parallel_test)

    config = BenchmarkConfig(
        quests=[str(quest_path)],
        agents=[HarnessConfig(model="random_choice", harness="random_choice", runs=4)],
        quest_timeout=5,
        max_workers=2,
        output_dir=str(tmp_path),
    )

    started = time.monotonic()
    results = run_benchmark(config)
    elapsed = time.monotonic() - started

    assert len(results) == 4
    assert elapsed < 5.0


@pytest.mark.timeout(10)
def test_run_benchmark_includes_max_steps_in_each_task(monkeypatch, tmp_path):
    """run_benchmark must thread BenchmarkConfig.max_steps into every queued
    task so _run_benchmark_task (running in a spawned child process) can see
    it. Substitutes the child-process entry point to avoid the cost/flakiness
    of a real subprocess+quest-engine run; the fake task reports what
    task['max_steps'] it actually received, back through the normal result
    channel (a local closure can't be pickled across the spawn boundary)."""
    quest_path = tmp_path / "quest.qm"
    quest_path.write_text("""
    [start]
    text: Done.
    failure: true
    """)

    monkeypatch.setattr(benchmark_module, "_run_benchmark_task", _task_reporting_max_steps_seen)

    config = BenchmarkConfig(
        quests=[str(quest_path)],
        agents=[HarnessConfig(model="random_choice", harness="random_choice", runs=1)],
        quest_timeout=5,
        max_steps=7,
        max_workers=1,
        output_dir=str(tmp_path),
    )

    results = run_benchmark(config)

    assert len(results) == 1
    assert results[0]["max_steps_seen"] == 7


@pytest.mark.timeout(10)
def test_run_benchmark_max_steps_defaults_to_none_in_tasks(monkeypatch, tmp_path):
    """Backward compatibility: a config without max_steps must thread None
    through, not silently invent a cap."""
    quest_path = tmp_path / "quest.qm"
    quest_path.write_text("""
    [start]
    text: Done.
    failure: true
    """)

    monkeypatch.setattr(benchmark_module, "_run_benchmark_task", _task_reporting_max_steps_seen)

    config = BenchmarkConfig(
        quests=[str(quest_path)],
        agents=[HarnessConfig(model="random_choice", harness="random_choice", runs=1)],
        quest_timeout=5,
        max_workers=1,
        output_dir=str(tmp_path),
    )

    results = run_benchmark(config)

    assert results[0]["max_steps_seen"] is None


def test_run_benchmark_task_forwards_max_steps_to_run_quest_with_timeout(monkeypatch):
    """_run_benchmark_task (the actual child-process entry point) must forward
    task['max_steps'] to run_quest_with_timeout. Called directly in-process
    (it is a plain function) with run_quest_with_timeout monkeypatched, so this
    checks the wiring without needing a real quest engine or subprocess."""
    captured = {}

    def fake_run_quest_with_timeout(quest, agent, **kwargs):  # noqa: ARG001
        captured.update(kwargs)
        return QuestOutcome.FAILURE

    monkeypatch.setattr(benchmark_module, "run_quest_with_timeout", fake_run_quest_with_timeout)
    monkeypatch.setattr(benchmark_module, "create_harness", lambda **kwargs: object())  # noqa: ARG005

    task = {
        "run_index": 1,
        "quest": "quests/Boat.qm",
        "attempt": 1,
        "agent_config": HarnessConfig(model="random_choice", harness="random_choice", runs=1),
        "benchmark_id": "bench_max_steps_1",
        "max_steps": 12,
    }

    class _FakeQueue:
        def put(self, message):  # noqa: ARG002
            return None

    benchmark_module._run_benchmark_task(task, _FakeQueue())

    assert captured["max_steps"] == 12


@pytest.mark.timeout(10)
def test_benchmark_enforces_child_process_timeout(monkeypatch, tmp_path):
    quest_path = tmp_path / "slow_quest.qm"
    quest_path.write_text("""
    [start]
    text: Slow.
    failure: true
    """)

    recorded_timeouts = []
    monkeypatch.setattr(benchmark_module, "_run_benchmark_task", _slow_task_for_timeout_test)
    monkeypatch.setattr(
        benchmark_module,
        "_mark_run_timeout",
        lambda run_id, quest, agent_config, benchmark_id, timeout: recorded_timeouts.append((quest, timeout)),
    )

    config = BenchmarkConfig(
        quests=[str(quest_path)],
        agents=[HarnessConfig(model="random_choice", harness="random_choice", runs=1)],
        quest_timeout=1,
        max_workers=1,
        output_dir=str(tmp_path),
    )

    started = time.monotonic()
    results = run_benchmark(config)
    elapsed = time.monotonic() - started

    assert elapsed < 3
    assert results[0]["outcome"] == QuestOutcome.TIMEOUT.name
    assert recorded_timeouts == [(str(quest_path), 1)]
