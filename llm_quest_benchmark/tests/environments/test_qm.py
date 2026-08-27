"""Tests for QM environment"""

import logging
import time

import pytest

from llm_quest_benchmark.constants import DEFAULT_QUEST
from llm_quest_benchmark.environments.qm import QMPlayerEnv
from llm_quest_benchmark.schemas.records import QuestSnapshot


def _now_ms() -> int:
    return int(time.time() * 1000)


def test_qm_env_lifecycle():
    """QM environment lifecycle - initialization, reset, step, close"""
    env = QMPlayerEnv(str(DEFAULT_QUEST))
    try:
        assert env.quest_file == str(DEFAULT_QUEST)
        assert env.snapshot is None

        snapshot = env.reset()
        assert isinstance(snapshot, QuestSnapshot)
        assert snapshot.observation
        assert snapshot.choices
        assert snapshot.saving, "reset must carry the full engine saving"
        assert snapshot.digest == snapshot.compute_digest()

        after = env.step(1, _now_ms())
        assert isinstance(after, QuestSnapshot)
        assert after.saving
        assert after.digest != snapshot.digest
    finally:
        env.close()


def test_qm_env_restore_reproduces_the_recorded_digest():
    """Exact engine restore must reproduce the recorded snapshot digest."""
    env = QMPlayerEnv(str(DEFAULT_QUEST))
    try:
        start = env.reset()
        env.step(1, _now_ms())

        restored = env.restore(start)

        assert restored.digest == start.digest
        assert restored.location_id == start.location_id
        assert env.snapshot.digest == start.digest
    finally:
        env.close()


def test_qm_env_restore_rejects_snapshot_without_saving():
    env = QMPlayerEnv(str(DEFAULT_QUEST))
    try:
        env.reset()
        with pytest.raises(ValueError, match="full engine saving"):
            env.restore(QuestSnapshot(location_id="1", observation="x", saving=None))
    finally:
        env.close()


def test_qm_env_error_handling():
    """QM environment error handling"""
    with pytest.raises(RuntimeError):
        QMPlayerEnv("nonexistent.qm")

    env = QMPlayerEnv(str(DEFAULT_QUEST))
    try:
        with pytest.raises(RuntimeError):
            env.step(1, _now_ms())
    finally:
        env.close()


def test_qm_env_rejects_invalid_choice():
    env = QMPlayerEnv(str(DEFAULT_QUEST))
    try:
        env.reset()
        with pytest.raises(RuntimeError):
            env.step(999, _now_ms())
    finally:
        env.close()


class _FakeBridgeState:
    def __init__(self, text: str):
        self.text = text


class _FakeBridge:
    def __init__(self, states):
        self.state_history = states

    def step(self, _choice_index, _performed_at_ms):
        raise AssertionError("step() should not be called when loop detection triggers")


def test_infinite_loop_detection_sets_terminal_failure_state():
    """Loop guard must produce a terminal snapshot, not a dangling non-final one."""
    env = QMPlayerEnv.__new__(QMPlayerEnv)
    env.debug = False
    env.language = "rus"
    env.forced_stop_reason = None
    env.logger = logging.getLogger("test_qm_loop_guard")
    env.bridge = _FakeBridge([_FakeBridgeState("Наступил новый день") for _ in range(31)])
    env._snapshot = QuestSnapshot(
        location_id="1",
        observation="Наступил новый день",
        choices=[{"id": "1", "text": "Ждать"}],
        params_state=["День: 10"],
        saving={"locationId": 1},
    )

    snapshot = env.step(1, _now_ms())

    assert snapshot.done is True
    assert snapshot.game_state == "fail"
    assert snapshot.choices == []
    assert "Forced stop" in snapshot.observation
    assert env.forced_stop_reason == "infinite_loop_detected"
