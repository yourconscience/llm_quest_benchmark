"""Tests for game_state-based outcome detection.

The TS engine provides authoritative gameState: "win" | "fail" | "dead" | "running".
The environment must use this directly, not text heuristics.
"""

import logging

from llm_quest_benchmark.schemas.bridge import QMBridgeState


def _make_bridge_state(game_state: str = "running", text: str = "", location_id: str = "1") -> QMBridgeState:
    return QMBridgeState(
        location_id=location_id,
        text=text,
        choices=[{"id": "1", "text": "Go"}] if game_state == "running" else [],
        reward=0.0,
        game_ended=game_state != "running",
        game_state=game_state,
    )


class TestQMBridgeStateGameState:
    def test_win_state(self):
        state = _make_bridge_state("win")
        assert state.game_ended is True
        assert state.game_state == "win"

    def test_fail_state(self):
        state = _make_bridge_state("fail")
        assert state.game_ended is True
        assert state.game_state == "fail"

    def test_dead_state(self):
        state = _make_bridge_state("dead")
        assert state.game_ended is True
        assert state.game_state == "dead"

    def test_running_state(self):
        state = _make_bridge_state("running")
        assert state.game_ended is False
        assert state.game_state == "running"

    def test_default_game_state(self):
        state = QMBridgeState(location_id="1", text="", choices=[], reward=0.0, game_ended=False)
        assert state.game_state == "running"


class TestEnvironmentOutcomeFromGameState:
    """Verify the environment determines success from game_state, not text."""

    def _make_env(self):
        from llm_quest_benchmark.environments.qm import QMPlayerEnv

        env = QMPlayerEnv.__new__(QMPlayerEnv)
        env.debug = False
        env.language = "eng"
        env.logger = logging.getLogger("test_outcome")
        env._current_state = {
            "location_id": "1",
            "text": "start",
            "params_state": [],
            "choices": [{"id": "1", "text": "Go"}],
            "reward": 0.0,
            "done": False,
            "info": {},
        }
        return env

    def _patch_bridge_step(self, env, game_state: str, text: str = ""):
        """Replace bridge.step to return a controlled state."""

        class FakeBridge:
            state_history = [_make_bridge_state("running")]

            def step(self, _action):
                return _make_bridge_state(game_state, text=text)

            def close(self):
                pass

        env.bridge = FakeBridge()

    def test_win_is_success(self):
        env = self._make_env()
        self._patch_bridge_step(env, "win")
        _, done, success, _ = env.step("1")
        assert done is True
        assert success is True

    def test_fail_is_failure(self):
        env = self._make_env()
        self._patch_bridge_step(env, "fail")
        _, done, success, _ = env.step("1")
        assert done is True
        assert success is False

    def test_dead_is_failure(self):
        env = self._make_env()
        self._patch_bridge_step(env, "dead")
        _, done, success, _ = env.step("1")
        assert done is True
        assert success is False

    def test_win_with_misleading_failure_text(self):
        """gameState=win must override misleading failure text."""
        env = self._make_env()
        self._patch_bridge_step(env, "win", text="mission failed completely, you died")
        _, done, success, _ = env.step("1")
        assert done is True
        assert success is True

    def test_fail_with_misleading_success_text(self):
        """gameState=fail must override misleading success text like 'congratulations'."""
        env = self._make_env()
        self._patch_bridge_step(env, "fail", text="congratulations on your 10000 credits reward")
        _, done, success, _ = env.step("1")
        assert done is True
        assert success is False

    def test_running_is_not_done(self):
        env = self._make_env()
        self._patch_bridge_step(env, "running")
        _, done, success, _ = env.step("1")
        assert done is False
        assert success is False
