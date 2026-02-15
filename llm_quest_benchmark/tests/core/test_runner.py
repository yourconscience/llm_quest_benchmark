"""Tests for runner timeout handling."""
from concurrent.futures import TimeoutError as FuturesTimeoutError
from types import SimpleNamespace

from llm_quest_benchmark.core.runner import run_quest_with_timeout
from llm_quest_benchmark.environments.state import QuestOutcome


def test_timeout_records_benchmark_id(monkeypatch):
    recorded = {}

    class DummyFuture:
        def result(self, timeout):  # noqa: ARG002
            raise FuturesTimeoutError()

        def cancel(self):
            return None

    class DummyExecutor:
        def __init__(self, max_workers):  # noqa: ARG002
            self.future = DummyFuture()

        def submit(self, fn, quest):  # noqa: ARG002
            return self.future

        def shutdown(self, wait=False, cancel_futures=True):  # noqa: ARG002
            return None

    class DummyLogger:
        def __init__(self, debug=False, agent=None):  # noqa: ARG002
            self.current_run_id = 1
            self.logger = SimpleNamespace(
                warning=lambda *a, **k: None,
                error=lambda *a, **k: None,
                info=lambda *a, **k: None,
            )

        def set_quest_file(self, quest_path):  # noqa: ARG002
            return None

        def _init_connection(self):
            return None

        def set_quest_outcome(self, outcome, reward, final_state=None, benchmark_id=None):
            recorded["outcome"] = outcome
            recorded["reward"] = reward
            recorded["final_state"] = final_state
            recorded["benchmark_id"] = benchmark_id

    class DummyRunner:
        def __init__(self, **kwargs):  # noqa: ARG002
            return None

        def run(self, quest):  # noqa: ARG002
            return QuestOutcome.SUCCESS

        def request_stop(self, reason):  # noqa: ARG002
            recorded["stop_reason"] = reason

        def snapshot_state(self):
            return {"location_id": "X", "done": False}

    monkeypatch.setattr("llm_quest_benchmark.core.runner.QuestLogger", DummyLogger)
    monkeypatch.setattr("llm_quest_benchmark.core.runner.QuestEnvironment", lambda *a, **k: object())
    monkeypatch.setattr("llm_quest_benchmark.core.runner.QuestRunner", DummyRunner)
    monkeypatch.setattr("llm_quest_benchmark.core.runner.ThreadPoolExecutor", DummyExecutor)

    agent = SimpleNamespace(agent_id="llm_test")
    cfg = SimpleNamespace(agent_id="llm_test", benchmark_id="bench_timeout_1")

    outcome = run_quest_with_timeout("quests/mock.qm", agent, timeout=1, agent_config=cfg)

    assert outcome == QuestOutcome.TIMEOUT
    assert recorded["stop_reason"] == "timeout"
    assert recorded["outcome"] == QuestOutcome.TIMEOUT.name
    assert recorded["benchmark_id"] == "bench_timeout_1"
    assert recorded["final_state"] == {"location_id": "X", "done": False}
