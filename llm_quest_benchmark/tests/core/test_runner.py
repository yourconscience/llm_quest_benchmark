"""Tests for runner transitions, truncation, checkpoints, and timeout handling."""

from concurrent.futures import TimeoutError as FuturesTimeoutError
from types import SimpleNamespace

import pytest

from llm_quest_benchmark.constants import DEFAULT_QUEST
from llm_quest_benchmark.core.runner import QuestRunner, run_quest_with_timeout
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.harnesses.specs import build_treatment
from llm_quest_benchmark.players.base import DecisionContext, QuestPlayer
from llm_quest_benchmark.schemas.records import QuestAction, QuestSnapshot
from llm_quest_benchmark.schemas.response import LLMResponse

QUEST = str(DEFAULT_QUEST)


def _snapshot(location_id: str, done: bool = False, game_state: str = "running", choices=None) -> QuestSnapshot:
    return QuestSnapshot(
        location_id=location_id,
        observation=f"Observation at {location_id}",
        choices=[] if done else (choices if choices is not None else [{"id": "11", "text": "Continue"}]),
        params_state=[f"Loc: {location_id}"],
        done=done,
        game_state=game_state,
        saving={"locationId": location_id},
    )


class _FakeEnv:
    """Snapshot-returning environment stub with checkpoint restore."""

    def __init__(self, terminate_at: int | None = None, success: bool = True):
        self.quest_file = QUEST
        self.language = "rus"
        self.forced_stop_reason = None
        self.terminate_at = terminate_at
        self.success = success
        self.taken = 0
        self.restored = []
        self._snapshot = None

    @property
    def snapshot(self):
        return self._snapshot

    def reset(self):
        self.taken = 0
        self._snapshot = _snapshot("loc0")
        return self._snapshot

    def step(self, choice_index, performed_at_ms):
        assert isinstance(performed_at_ms, int) and performed_at_ms > 0
        self.taken += 1
        done = self.terminate_at is not None and self.taken >= self.terminate_at
        game_state = "running" if not done else ("win" if self.success else "fail")
        self._snapshot = _snapshot(f"loc{self.taken}", done=done, game_state=game_state)
        return self._snapshot

    def restore(self, snapshot):
        self.restored.append(snapshot.location_id)
        self._snapshot = snapshot
        return snapshot

    def close(self):
        return None


class _FakeAgent(QuestPlayer):
    def __init__(self):
        super().__init__()
        self.action_calls = 0
        self.transitions = []
        self.agent_id = "fake_agent"
        self.harness_name = "human"

    def reset(self):
        return None

    def on_game_start(self):
        return None

    def on_game_end(self, final_snapshot):
        return None

    def on_transition(self, transition):
        self.transitions.append(transition)

    def _get_action_impl(self, observation, choices):
        self.action_calls += 1
        self._last_response = LLMResponse(action=1)
        return 1

    def __str__(self):
        return "FakeAgent"


class _RestoringAgent(_FakeAgent):
    """Emits one restore to checkpoint 1 on its third decision."""

    supports_restore = True

    def __init__(self):
        super().__init__()
        self.contexts = []

    def get_quest_action(self, observation, choices, context: DecisionContext) -> QuestAction:
        self.contexts.append(context)
        self.action_calls += 1
        self._last_response = LLMResponse(action=1)
        if self.action_calls == 3 and context.restore_allowed:
            return QuestAction.restore(1)
        return QuestAction(kind="choose", choice_index=1)


class _FakeConfig:
    """Minimal agent config exposing the canonical treatment the runner records."""

    def __init__(self, agent_id="fake_agent_id", benchmark_id=None, restore_limit=None):
        self.agent_id = agent_id
        self.benchmark_id = benchmark_id
        self.restore_limit = restore_limit

    def treatment(self):
        return build_treatment(
            harness="reasoning_recent",
            model="gpt-5-mini",
            temperature=0.4,
            system_template="system_role.jinja",
        )


class _DummyQuestLogger:
    def __init__(self):
        self.current_run_id = 1
        self.started = None
        self.transitions = []
        self.outcomes = []

    def start_run(self, **kwargs):
        self.started = kwargs
        return 1

    def log_transition(self, transition):
        self.transitions.append(transition)

    def adopt_transitions(self, transitions):
        for transition in transitions:
            self.log_transition(transition)

    def finish_run(self, outcome, reward=0.0, terminal_snapshot=None, progress=None, diagnostics=None):
        self.outcomes.append(
            {
                "outcome": outcome,
                "reward": reward,
                "terminal_snapshot": terminal_snapshot,
                "progress": progress,
                "diagnostics": diagnostics,
            }
        )


def _runner(monkeypatch, env, agent, **kwargs):
    monkeypatch.setattr("llm_quest_benchmark.core.runner.QuestEnvironment", lambda *a, **k: env)
    logger = _DummyQuestLogger()
    runner = QuestRunner(agent=agent, quest_logger=logger, **kwargs)
    return runner, logger


def test_run_records_one_transition_per_executed_action(monkeypatch):
    env = _FakeEnv(terminate_at=3)
    agent = _FakeAgent()
    runner, logger = _runner(monkeypatch, env, agent)

    outcome = runner.run(QUEST)

    assert outcome == QuestOutcome.SUCCESS
    assert agent.action_calls == 3
    assert len(logger.transitions) == 3
    # No synthetic terminal decision row: terminal state is the last after-snapshot.
    assert logger.transitions[-1].after.done is True
    assert logger.outcomes[-1]["terminal_snapshot"] is logger.transitions[-1].after
    assert [t.index for t in logger.transitions] == [1, 2, 3]
    assert agent.transitions == logger.transitions


def test_transition_carries_before_action_and_after(monkeypatch):
    env = _FakeEnv(terminate_at=1)
    agent = _FakeAgent()
    runner, logger = _runner(monkeypatch, env, agent)

    runner.run(QUEST)
    transition = logger.transitions[0]

    assert transition.before.location_id == "loc0"
    assert transition.after.location_id == "loc1"
    assert transition.action.is_choose
    assert transition.action.choice_index == 1
    assert transition.action.choice_id == "11"
    assert transition.action.performed_at_ms is not None
    assert transition.provenance == "runtime"


def test_run_metadata_is_initialized_before_execution(monkeypatch):
    env = _FakeEnv(terminate_at=1)
    agent = _FakeAgent()
    runner, logger = _runner(monkeypatch, env, agent)

    runner.run(QUEST)

    assert logger.started["quest_file"] == QUEST
    assert logger.started["quest_checksum"].startswith("sha256:")
    assert logger.started["engine_revision"]
    assert logger.started["treatment"]["signature"].startswith("t2_")


def test_max_steps_none_preserves_unbounded_loop(monkeypatch):
    """Omitting max_steps must not cut a quest short before its terminal state."""
    env = _FakeEnv(terminate_at=5)
    agent = _FakeAgent()
    runner, logger = _runner(monkeypatch, env, agent, max_steps=None)

    outcome = runner.run(QUEST)

    assert outcome == QuestOutcome.SUCCESS
    assert agent.action_calls == 5
    assert runner.step_count == 5
    assert logger.outcomes[-1]["outcome"] == QuestOutcome.SUCCESS.name


def test_max_steps_records_resumable_truncated_outcome(monkeypatch):
    """An explicit step limit is a deliberate stop, not a quest failure."""
    env = _FakeEnv(terminate_at=None)
    agent = _FakeAgent()
    runner, logger = _runner(monkeypatch, env, agent, max_steps=3)

    outcome = runner.run(QUEST)

    assert outcome == QuestOutcome.TRUNCATED
    assert outcome.is_resumable
    assert agent.action_calls == 3
    assert len(logger.transitions) == 3
    assert logger.outcomes[-1]["outcome"] == QuestOutcome.TRUNCATED.name


def test_max_steps_larger_than_natural_termination_does_not_interfere(monkeypatch):
    env = _FakeEnv(terminate_at=2)
    agent = _FakeAgent()
    runner, _ = _runner(monkeypatch, env, agent, max_steps=60)

    assert runner.run(QUEST) == QuestOutcome.SUCCESS
    assert agent.action_calls == 2


def test_backtracking_restore_truncates_only_the_active_branch(monkeypatch):
    env = _FakeEnv(terminate_at=5)
    agent = _RestoringAgent()
    runner, logger = _runner(monkeypatch, env, agent, max_steps=6)

    runner.run(QUEST)

    restores = [t for t in logger.transitions if t.action.is_restore]
    assert len(restores) == 1
    assert restores[0].action.checkpoint_index == 1
    # The restore is visible in the chronological log, before and after it.
    assert len(logger.transitions) > 1
    assert env.restored == ["loc0"]
    assert runner._restores_accepted == 1
    assert logger.outcomes[-1]["diagnostics"]["restore"]["accepted"] == 1


def test_restore_is_rejected_for_harnesses_without_the_capability(monkeypatch):
    class _SneakyAgent(_FakeAgent):
        def get_quest_action(self, observation, choices, context):
            self.action_calls += 1
            self._last_response = LLMResponse(action=1)
            return QuestAction.restore(1)

    env = _FakeEnv(terminate_at=2)
    agent = _SneakyAgent()
    runner, logger = _runner(monkeypatch, env, agent, max_steps=4)

    runner.run(QUEST)

    assert not any(t.action.is_restore for t in logger.transitions)
    assert env.restored == []
    assert runner._restore_attempts > 0
    assert runner._restores_accepted == 0


def test_restore_limit_closes_the_budget(monkeypatch):
    env = _FakeEnv(terminate_at=None)
    agent = _RestoringAgent()
    runner, _ = _runner(
        monkeypatch,
        env,
        agent,
        max_steps=6,
        agent_config=_FakeConfig(restore_limit=1),
    )

    runner.run(QUEST)

    assert runner._restores_accepted <= 1
    # Once the budget is spent the runner stops offering restore.
    assert agent.contexts[-1].restores_remaining == 0
    assert agent.contexts[-1].restore_allowed is False


def test_timeout_records_outcome_and_final_snapshot(monkeypatch):
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

        def finish_run(self, outcome, reward=0.0, terminal_snapshot=None, progress=None, diagnostics=None):
            recorded.update(
                {
                    "outcome": outcome,
                    "reward": reward,
                    "terminal_snapshot": terminal_snapshot,
                    "diagnostics": diagnostics,
                }
            )

    class DummyRunner:
        def __init__(self, **kwargs):  # noqa: ARG002
            return None

        def run(self, quest):  # noqa: ARG002
            return QuestOutcome.SUCCESS

        def request_stop(self, reason):
            recorded["stop_reason"] = reason

        def current_snapshot(self):
            return _snapshot("loc7")

        def progress_state(self):
            return None

        def runtime_metrics(self):
            return {"restore": {"attempts": 0}}

    monkeypatch.setattr("llm_quest_benchmark.core.runner.QuestLogger", DummyLogger)
    monkeypatch.setattr("llm_quest_benchmark.core.runner.QuestRunner", DummyRunner)
    monkeypatch.setattr("llm_quest_benchmark.core.runner.ThreadPoolExecutor", DummyExecutor)

    agent = SimpleNamespace(agent_id="llm_test")
    cfg = SimpleNamespace(agent_id="llm_test", benchmark_id="bench_timeout_1")

    outcome = run_quest_with_timeout(QUEST, agent, timeout=1, agent_config=cfg)

    assert outcome == QuestOutcome.TIMEOUT
    assert recorded["stop_reason"] == "timeout"
    assert recorded["outcome"] == QuestOutcome.TIMEOUT.name
    assert recorded["terminal_snapshot"].location_id == "loc7"


def test_run_quest_with_timeout_forwards_options_to_runner(monkeypatch):
    captured = {}

    class DummyLogger:
        def __init__(self, debug=False, agent=None):  # noqa: ARG002
            self.current_run_id = 1
            self.logger = SimpleNamespace(
                warning=lambda *a, **k: None, error=lambda *a, **k: None, info=lambda *a, **k: None
            )

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
    monkeypatch.setattr("llm_quest_benchmark.core.runner.QuestRunner", fake_quest_runner)
    monkeypatch.setattr("llm_quest_benchmark.core.runner.ThreadPoolExecutor", DummyExecutorForResult)

    agent = SimpleNamespace(agent_id="llm_test")
    outcome = run_quest_with_timeout(
        QUEST, agent, timeout=1, max_steps=42, progress_manifest="configs/progress/Boat.yaml"
    )

    assert outcome == QuestOutcome.SUCCESS
    assert captured["max_steps"] == 42
    assert captured["progress_manifest"] == "configs/progress/Boat.yaml"


def test_run_uses_agent_config_identity_for_the_run(monkeypatch):
    """Identity comes from the treatment config, not from a post-export patch."""
    env = _FakeEnv(terminate_at=1)
    agent = _FakeAgent()
    config = _FakeConfig(agent_id="gpt-5-mini_t0.4_reasoning_recent_deadbeef", benchmark_id="bench_1")
    monkeypatch.setattr("llm_quest_benchmark.core.runner.QuestEnvironment", lambda *a, **k: env)
    logger = _DummyQuestLogger()
    runner = QuestRunner(agent=agent, quest_logger=logger, agent_config=config)

    runner.run(QUEST)

    assert logger.started["agent_id"] == "gpt-5-mini_t0.4_reasoning_recent_deadbeef"
    assert logger.started["benchmark_id"] == "bench_1"


def test_progress_is_monotonic_and_terminal_success_is_full(monkeypatch, tmp_path):
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        """
quest: Fake
version: 1
milestones:
  - id: first
    percent: 40
    match:
      location_id: ["loc1"]
""",
        encoding="utf-8",
    )

    env = _FakeEnv(terminate_at=3)
    agent = _FakeAgent()
    runner, logger = _runner(monkeypatch, env, agent, progress_manifest=str(manifest))

    runner.run(QUEST)

    progress_values = [t.progress.current for t in logger.transitions]
    assert progress_values == sorted(progress_values)
    assert progress_values[0] == pytest.approx(40.0)
    assert progress_values[-1] == pytest.approx(100.0)
