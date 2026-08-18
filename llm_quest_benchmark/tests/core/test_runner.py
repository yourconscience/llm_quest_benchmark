"""Tests for runner timeout and max-steps handling."""

from concurrent.futures import TimeoutError as FuturesTimeoutError
from types import SimpleNamespace

from llm_quest_benchmark.core.runner import QuestRunner, run_quest_with_timeout
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


class _NonTerminatingEnv:
    """Fake quest environment with a single choice that never ends the quest."""

    def __init__(self):
        self.state = {"choices": [{"text": "Continue"}], "location_id": "loc", "reward": 0.0}

    def reset(self):
        return "Same observation forever."

    def step(self, action):  # noqa: ARG002
        return "Same observation forever.", False, False, {}


class _TerminatingEnv:
    """Fake quest environment that ends successfully after `terminate_at` steps."""

    def __init__(self, terminate_at: int):
        self.terminate_at = terminate_at
        self._taken = 0
        self.state = {"choices": [{"text": "Continue"}], "location_id": "loc", "reward": 0.0}

    def reset(self):
        return "Initial observation."

    def step(self, action):  # noqa: ARG002
        self._taken += 1
        done = self._taken >= self.terminate_at
        if done:
            self.state = {"choices": [], "location_id": "loc", "reward": 1.0}
        return "Observation.", done, done, {}


class _FakeAgent:
    def __init__(self):
        self.action_calls = 0

    def reset(self):
        return None

    def on_game_start(self):
        return None

    def on_game_end(self, final_state):  # noqa: ARG002
        return None

    def get_action(self, observation, choices):  # noqa: ARG002
        self.action_calls += 1
        return 1

    def get_last_response(self):
        return None

    def __str__(self):
        return "FakeAgent"


class _DummyQuestLogger:
    def __init__(self):
        self.current_run_id = 1
        self.steps_logged = 0
        self.outcomes = []

    def set_quest_file(self, quest_path):  # noqa: ARG002
        return None

    def log_step(self, agent_state):  # noqa: ARG002
        self.steps_logged += 1

    def set_quest_outcome(self, outcome, reward, benchmark_id=None, final_state=None):
        self.outcomes.append(
            {"outcome": outcome, "reward": reward, "benchmark_id": benchmark_id, "final_state": final_state}
        )


def test_max_steps_none_preserves_unbounded_loop(monkeypatch):
    """Backward compatibility: omitting max_steps (None) must not cut a quest
    short before its natural terminal state, regardless of step count."""
    env = _TerminatingEnv(terminate_at=5)
    monkeypatch.setattr("llm_quest_benchmark.core.runner.QuestEnvironment", lambda *a, **k: env)

    agent = _FakeAgent()
    quest_logger = _DummyQuestLogger()
    runner = QuestRunner(agent=agent, quest_logger=quest_logger, max_steps=None)

    outcome = runner.run("quests/mock.qm")

    assert outcome == QuestOutcome.SUCCESS
    assert agent.action_calls == 5
    assert runner.step_count == 5
    assert quest_logger.outcomes[-1]["outcome"] == QuestOutcome.SUCCESS.name


def test_max_steps_caps_a_non_terminating_quest_as_failure(monkeypatch):
    """A quest that never reaches a terminal state must stop at max_steps and
    be recorded as FAILURE, not loop forever."""
    env = _NonTerminatingEnv()
    monkeypatch.setattr("llm_quest_benchmark.core.runner.QuestEnvironment", lambda *a, **k: env)

    agent = _FakeAgent()
    quest_logger = _DummyQuestLogger()
    runner = QuestRunner(agent=agent, quest_logger=quest_logger, max_steps=3)

    outcome = runner.run("quests/mock.qm")

    assert outcome == QuestOutcome.FAILURE
    assert agent.action_calls == 3  # exactly max_steps actions taken, no more
    assert runner.step_count == 3
    assert quest_logger.outcomes  # the cap path must record an outcome, not just return
    assert quest_logger.outcomes[-1]["outcome"] == QuestOutcome.FAILURE.name


def test_max_steps_larger_than_natural_termination_does_not_interfere(monkeypatch):
    """A generous max_steps must not change the outcome of a quest that
    terminates naturally well before the cap."""
    env = _TerminatingEnv(terminate_at=2)
    monkeypatch.setattr("llm_quest_benchmark.core.runner.QuestEnvironment", lambda *a, **k: env)

    agent = _FakeAgent()
    quest_logger = _DummyQuestLogger()
    runner = QuestRunner(agent=agent, quest_logger=quest_logger, max_steps=60)

    outcome = runner.run("quests/mock.qm")

    assert outcome == QuestOutcome.SUCCESS
    assert agent.action_calls == 2
    assert runner.step_count == 2


def test_run_quest_with_timeout_forwards_max_steps_to_runner(monkeypatch):
    """run_quest_with_timeout must thread max_steps through to QuestRunner."""
    captured = {}

    class DummyLogger:
        def __init__(self, debug=False, agent=None):  # noqa: ARG002
            self.current_run_id = 1
            self.logger = SimpleNamespace(
                warning=lambda *a, **k: None, error=lambda *a, **k: None, info=lambda *a, **k: None
            )

        def set_quest_file(self, quest_path):  # noqa: ARG002
            return None

    class DummyExecutorForResult:
        def __init__(self, max_workers):  # noqa: ARG002
            pass

        def submit(self, fn, quest):  # noqa: ARG002
            class _Fut:
                def result(self, timeout):  # noqa: ARG002
                    return QuestOutcome.SUCCESS

            return _Fut()

        def shutdown(self, wait=False, cancel_futures=True):  # noqa: ARG002
            return None

    def fake_quest_runner(**kwargs):
        captured.update(kwargs)

        class _Runner:
            def run(self, quest):  # noqa: ARG002
                return QuestOutcome.SUCCESS

        return _Runner()

    monkeypatch.setattr("llm_quest_benchmark.core.runner.QuestLogger", DummyLogger)
    monkeypatch.setattr("llm_quest_benchmark.core.runner.QuestEnvironment", lambda *a, **k: object())
    monkeypatch.setattr("llm_quest_benchmark.core.runner.QuestRunner", fake_quest_runner)
    monkeypatch.setattr("llm_quest_benchmark.core.runner.ThreadPoolExecutor", DummyExecutorForResult)

    agent = SimpleNamespace(agent_id="llm_test")
    outcome = run_quest_with_timeout("quests/mock.qm", agent, timeout=1, max_steps=42)

    assert outcome == QuestOutcome.SUCCESS
    assert captured["max_steps"] == 42
