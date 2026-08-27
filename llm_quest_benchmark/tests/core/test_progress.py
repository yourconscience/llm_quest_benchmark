"""Tests for state-based progress manifests and the monotonic tracker."""

from pathlib import Path

import pytest

from llm_quest_benchmark.core.progress import ProgressManifest, ProgressTracker, load_progress_manifest
from llm_quest_benchmark.schemas.records import QuestSnapshot

BOAT_MANIFEST = Path(__file__).resolve().parents[3] / "configs" / "progress" / "Boat.yaml"


def _snapshot(location_id="1", params=None, observation="text", game_state="running", done=False) -> QuestSnapshot:
    return QuestSnapshot(
        location_id=location_id,
        observation=observation,
        choices=[{"id": "11", "text": "Continue"}],
        params_state=params or [],
        game_state=game_state,
        done=done,
        saving={"locationId": location_id},
    )


def _manifest(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "manifest.yaml"
    path.write_text(body, encoding="utf-8")
    return path


VALID_BODY = """
quest: Demo
version: 1
milestones:
  - id: entered
    percent: 25
    match:
      location_id: ["2"]
  - id: armed
    percent: 60
    match:
      params_contains: ["Sword"]
  - id: two_across
    percent: 80
    match:
      params_pattern:
        pattern: "^xxx - "
        min_count: 2
"""


def test_manifest_validates_and_loads(tmp_path):
    manifest = ProgressManifest.from_file(_manifest(tmp_path, VALID_BODY))

    assert manifest.quest == "Demo"
    assert [m.id for m in manifest.milestones] == ["entered", "armed", "two_across"]
    assert manifest.maximum == 100.0


def test_manifest_rejects_duplicate_ids(tmp_path):
    body = VALID_BODY.replace("id: armed", "id: entered")
    with pytest.raises(ValueError, match="Duplicate milestone id"):
        ProgressManifest.from_file(_manifest(tmp_path, body))


def test_manifest_rejects_descending_percentages(tmp_path):
    body = VALID_BODY.replace("percent: 60", "percent: 10")
    with pytest.raises(ValueError, match="percent decreases"):
        ProgressManifest.from_file(_manifest(tmp_path, body))


def test_manifest_rejects_out_of_range_percent(tmp_path):
    body = VALID_BODY.replace("percent: 60", "percent: 160")
    with pytest.raises(ValueError, match="within 0..100"):
        ProgressManifest.from_file(_manifest(tmp_path, body))


def test_manifest_rejects_unknown_predicates(tmp_path):
    body = VALID_BODY.replace('      location_id: ["2"]', "      vibes: high")
    with pytest.raises(ValueError, match="unknown predicates"):
        ProgressManifest.from_file(_manifest(tmp_path, body))


def test_manifest_rejects_empty_milestones(tmp_path):
    with pytest.raises(ValueError, match="non-empty 'milestones' list"):
        ProgressManifest.from_file(_manifest(tmp_path, "quest: Demo\nversion: 1\nmilestones: []\n"))


def test_manifest_rejects_unsupported_version(tmp_path):
    with pytest.raises(ValueError, match="Unsupported progress manifest version"):
        ProgressManifest.from_file(_manifest(tmp_path, VALID_BODY.replace("version: 1", "version: 7")))


def test_predicates_match_location_params_and_pattern(tmp_path):
    manifest = ProgressManifest.from_file(_manifest(tmp_path, VALID_BODY))
    entered, armed, two_across = manifest.milestones

    assert entered.matches(_snapshot(location_id="2"))
    assert not entered.matches(_snapshot(location_id="3"))
    assert armed.matches(_snapshot(params=["Sword of dawn"]))
    assert not armed.matches(_snapshot(params=["Shield"]))
    assert two_across.matches(_snapshot(params=["xxx - Ах(2)", "xxx - Вау(1)"]))
    assert not two_across.matches(_snapshot(params=["xxx - Ах(2)", "Вау (1) - xxx"]))


def test_progress_is_monotonic_across_a_restore(tmp_path):
    tracker = ProgressTracker(manifest=ProgressManifest.from_file(_manifest(tmp_path, VALID_BODY)))

    tracker.seed(_snapshot(location_id="1"))
    advanced = tracker.observe(_snapshot(location_id="2"))
    assert advanced.current == pytest.approx(25.0)
    assert advanced.newly_reached == ["entered"]

    # Restoring to the starting state must not lower recorded progress.
    after_restore = tracker.observe(_snapshot(location_id="1"))
    assert after_restore.current == pytest.approx(25.0)
    assert after_restore.newly_reached == []
    assert after_restore.reached == ["entered"]


def test_stall_counter_resets_on_a_new_milestone(tmp_path):
    tracker = ProgressTracker(manifest=ProgressManifest.from_file(_manifest(tmp_path, VALID_BODY)))
    tracker.seed(_snapshot(location_id="1"))

    assert tracker.observe(_snapshot(location_id="1")).stalled_transitions == 1
    assert tracker.observe(_snapshot(location_id="1")).stalled_transitions == 2
    assert tracker.observe(_snapshot(location_id="2")).stalled_transitions == 0
    assert tracker.observe(_snapshot(location_id="2")).stalled_transitions == 1


def test_terminal_success_is_always_full_progress(tmp_path):
    tracker = ProgressTracker(manifest=ProgressManifest.from_file(_manifest(tmp_path, VALID_BODY)))
    tracker.seed(_snapshot(location_id="1"))

    state = tracker.observe(_snapshot(location_id="9", game_state="win", done=True))

    assert state.current == pytest.approx(100.0)
    assert state.maximum == pytest.approx(100.0)


def test_without_a_manifest_progress_is_terminal_only():
    """No manifest means no guessing: only terminal success moves the needle."""
    tracker = ProgressTracker(manifest=None)
    tracker.seed(_snapshot(location_id="1"))

    assert tracker.observe(_snapshot(location_id="5")).current == 0.0
    assert tracker.observe(_snapshot(location_id="9", game_state="fail", done=True)).current == 0.0

    winning = ProgressTracker(manifest=None)
    assert winning.observe(_snapshot(game_state="win", done=True)).current == pytest.approx(100.0)


def test_restore_from_seeds_a_resumed_tracker(tmp_path):
    tracker = ProgressTracker(manifest=ProgressManifest.from_file(_manifest(tmp_path, VALID_BODY)))
    tracker.seed(_snapshot(location_id="1"))
    tracker.observe(_snapshot(location_id="2"))
    state = tracker.state()

    resumed = ProgressTracker(manifest=tracker.manifest)
    resumed.restore_from(state)

    assert resumed.state().current == pytest.approx(25.0)
    assert resumed.state().reached == ["entered"]
    # Already-reached milestones are not re-awarded on resume.
    assert resumed.observe(_snapshot(location_id="2")).newly_reached == []


def test_bundled_boat_manifest_is_valid_and_state_based():
    manifest = load_progress_manifest(str(BOAT_MANIFEST))

    assert manifest is not None
    assert manifest.quest == "Boat"
    ids = [m.id for m in manifest.milestones]
    assert "crossing_started" in ids
    assert "all_gods_across" in ids

    tracker = ProgressTracker(manifest=manifest)
    tracker.seed(_snapshot(location_id="1"))
    state = tracker.observe(
        _snapshot(
            location_id="6",
            params=[
                "Осталось 11 часов",
                "Положение Богов:",
                "xxx - Ах(2)",
                "xxx - Бах(5)",
                "Вау (1) - xxx",
                "Гэ (10) - xxx",
            ],
        )
    )

    assert "crossing_started" in state.reached
    assert "two_gods_across" in state.reached
    assert "three_gods_across" not in state.reached
    assert state.current == pytest.approx(70.0)


def test_load_progress_manifest_returns_none_without_a_path():
    assert load_progress_manifest(None) is None
    assert load_progress_manifest("") is None
