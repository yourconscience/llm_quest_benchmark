"""End-to-end truncate/resume and restore against the real QM engine."""

import json
from pathlib import Path

import pytest

from llm_quest_benchmark.core import logging as logging_module
from llm_quest_benchmark.core.replay import harness_config_from_record, replay_record, verify_environment
from llm_quest_benchmark.core.runner import run_quest_with_timeout
from llm_quest_benchmark.environments.qm import QMPlayerEnv
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.harnesses.factory import create_harness
from llm_quest_benchmark.schemas.config import HarnessConfig
from llm_quest_benchmark.schemas.records import load_run_record

REPO_ROOT = Path(__file__).resolve().parents[3]
BOAT = str(REPO_ROOT / "quests" / "Boat.qm")
HARNESS = "random_choice_7"
MAX_STEPS = 6


@pytest.fixture
def isolated_results(tmp_path, monkeypatch):
    """Keep run records and the metrics database inside the test directory."""
    monkeypatch.setattr(logging_module, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(logging_module, "DEFAULT_DB_PATH", str(tmp_path / "metrics.db"))
    return tmp_path


def _config() -> HarnessConfig:
    return HarnessConfig(harness=HARNESS, model="random_choice", skip_single=False)


def _agent():
    return create_harness(harness=HARNESS, model="random_choice", skip_single=False)


def _run(max_steps, resume_record=None, resume_path=None) -> QuestOutcome:
    return run_quest_with_timeout(
        quest_path=BOAT,
        agent=_agent(),
        timeout=120,
        agent_config=_config(),
        max_steps=max_steps,
        resume_record=resume_record,
        resume_path=resume_path,
    )


def _latest_record(results_dir: Path):
    summaries = sorted(
        results_dir.rglob("run_summary.json"),
        key=lambda path: int(path.parent.name.split("_", 1)[1]),
    )
    assert summaries, "expected at least one exported run record"
    return summaries[-1], load_run_record(str(summaries[-1]))


def _actions(record):
    return [(t.action.kind, t.action.choice_index, t.action.checkpoint_index) for t in record.transitions]


def _quest_state(snapshot):
    """Observable quest state, excluding engine bookkeeping.

    Two independently executed runs stamp their own wall-clock time into the
    engine saving's performedJumps log, so the raw saving (and therefore the
    snapshot digest) cannot match across runs. Everything the quest actually
    presents must.
    """
    return (
        snapshot.location_id,
        snapshot.observation,
        tuple(snapshot.params_state),
        tuple((c["id"], c["text"]) for c in snapshot.choices),
        snapshot.game_state,
        snapshot.done,
    )


@pytest.mark.integration
@pytest.mark.timeout(180)
def test_truncated_run_resumes_to_the_same_state_as_an_uninterrupted_run(isolated_results):
    results_dir = isolated_results / "results"

    # 1. Uninterrupted reference run.
    assert _run(MAX_STEPS) == QuestOutcome.TRUNCATED
    _, reference = _latest_record(results_dir)
    assert len(reference.transitions) == MAX_STEPS

    # 2. Truncate early, then resume from the record.
    assert _run(3) == QuestOutcome.TRUNCATED
    truncated_path, truncated = _latest_record(results_dir)
    assert truncated.outcome == "TRUNCATED"
    assert truncated.is_resumable
    assert len(truncated.transitions) == 3

    assert _run(MAX_STEPS, resume_record=truncated, resume_path=str(truncated_path)) == QuestOutcome.TRUNCATED
    _, resumed = _latest_record(results_dir)

    # Prior transitions are preserved and the run reaches the same state.
    assert len(resumed.transitions) == MAX_STEPS
    assert _actions(resumed) == _actions(reference)
    assert _quest_state(resumed.terminal_snapshot) == _quest_state(reference.terminal_snapshot)
    assert resumed.lineage is not None
    assert resumed.lineage.source_run_id == truncated.run_id
    assert resumed.lineage.resumed_from_index == 3


@pytest.mark.integration
@pytest.mark.timeout(180)
def test_recorded_run_replays_against_the_real_engine(isolated_results):
    results_dir = isolated_results / "results"
    assert _run(4) == QuestOutcome.TRUNCATED
    _, record = _latest_record(results_dir)

    verify_environment(record, record.quest_file)
    env = QMPlayerEnv(record.quest_file, language=record.quest_language)
    try:
        result = replay_record(env, record)
    finally:
        env.close()

    assert result.verified_transitions == len(record.transitions)
    assert result.snapshot.digest == record.transitions[-1].after.digest


@pytest.mark.integration
@pytest.mark.timeout(180)
def test_restore_returns_to_the_exact_recorded_checkpoint(isolated_results):
    """A real restore reproduces the recorded snapshot digest exactly."""
    env = QMPlayerEnv(BOAT)
    try:
        start = env.reset()
        checkpoints = [start]
        for step in range(3):
            checkpoints.append(env.step(1, 1735689600000 + step))

        restored = env.restore(checkpoints[1])

        assert restored.digest == checkpoints[1].digest
        assert restored.saving == checkpoints[1].saving
        # The engine really moved: continuing from here matches the branch again.
        assert env.snapshot.digest == checkpoints[1].digest
    finally:
        env.close()


@pytest.mark.integration
@pytest.mark.timeout(180)
def test_resume_is_rejected_when_the_quest_changed(isolated_results, tmp_path):
    results_dir = isolated_results / "results"
    assert _run(2) == QuestOutcome.TRUNCATED
    path, record = _latest_record(results_dir)

    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["quest"]["checksum"] = "sha256:not-this-quest"
    tampered_path = tmp_path / "tampered.json"
    tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
    tampered_record = load_run_record(str(tampered_path))

    with pytest.raises(Exception, match="Quest checksum mismatch"):
        _run(4, resume_record=tampered_record, resume_path=str(tampered_path))

    # Nothing about the original record changed.
    assert load_run_record(str(path)).quest_checksum == record.quest_checksum


@pytest.mark.integration
@pytest.mark.timeout(180)
def test_resume_config_is_rebuilt_from_the_record(isolated_results):
    results_dir = isolated_results / "results"
    assert _run(2) == QuestOutcome.TRUNCATED
    _, record = _latest_record(results_dir)

    config = harness_config_from_record(record)

    assert config.harness == HARNESS
    assert config.model == "random_choice"
    assert config.treatment().signature == record.treatment_signature
