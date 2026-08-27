import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "import_human_trace.py"


def load_module():
    spec = importlib.util.spec_from_file_location("import_human_trace", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _snapshot(location_id, observation, choices, saving):
    return {
        "location_id": location_id,
        "canonical_location_id": location_id,
        "observation": observation,
        "params": ["money: 10"],
        "choices": choices,
        "game_state": "running",
        "saving": saving,
    }


def _trace():
    dock = _snapshot("42", "You are at the dock.", {"1": "Board the ship", "2": "Go home"}, {"locationId": 42})
    deck = _snapshot("43", "You are on deck.", {"1": "Sail"}, {"locationId": 43})
    return {
        "schema_version": "human_trace_v2",
        "source": "web_play",
        "quest_id": "Boat",
        "quest_title": "Boat",
        "quest_lang": "en",
        "started_at": "2026-05-21T12:00:00.000Z",
        "ended_at": "2026-05-21T12:01:00.000Z",
        "outcome": "SUCCESS",
        "transitions": [
            {
                "index": 1,
                "kind": "choose",
                "before": dock,
                "action": {
                    "kind": "choose",
                    "choice_index": "1",
                    "choice_text": "Board the ship",
                    "jump_id": 7,
                    "performed_at_ms": None,
                },
                "after": deck,
            },
            {
                "index": 2,
                "kind": "restore",
                "before": deck,
                "action": {"kind": "restore", "checkpoint_index": 1},
                "after": dock,
            },
        ],
        "terminal": {"game_state": "win", "text": "Victory"},
    }


def test_import_human_trace_converts_to_schema_v2_record(tmp_path):
    module = load_module()
    raw_trace = _trace()
    input_path = tmp_path / "human_trace_Boat.json"
    output_path = tmp_path / "run_summary.json"
    input_path.write_text(json.dumps(raw_trace), encoding="utf-8")

    record = module.convert_trace(raw_trace, source_trace=str(input_path))
    module.write_summary(record, output_path)

    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved["schema_version"] == 2
    assert saved["quest"]["name"] == "Boat"
    assert saved["run"]["agent_id"] == "human_web"
    assert saved["treatment"]["harness"] == "human"
    assert saved["terminal"]["outcome"] == "SUCCESS"
    assert saved["usage"]["total_tokens"] == 0

    first = saved["transitions"][0]
    assert first["before"]["observation"] == "You are at the dock."
    assert [c["text"] for c in first["before"]["choices"]] == ["Board the ship", "Go home"]
    assert first["action"]["choice_index"] == 1
    assert first["before"]["saving"] == {"locationId": 42}
    # The browser cannot observe the engine timestamp, so replay stays unavailable.
    assert first["action"]["performed_at_ms"] is None
    assert first["replay_status"] == "unavailable"


def test_import_human_trace_keeps_restore_transitions(tmp_path):
    """Undone steps stay in the record; a restore is an explicit transition."""
    module = load_module()

    record = module.convert_trace(_trace())
    saved = record.to_dict()

    assert len(saved["transitions"]) == 2
    restore = saved["transitions"][1]
    assert restore["action"]["kind"] == "restore"
    assert restore["action"]["checkpoint_index"] == 1
    assert restore["after"]["location_id"] == "42"
    assert saved["transcript_diagnostics"]["restore_transitions"] == 1
    assert saved["transcript_diagnostics"]["total_steps"] == 1


def test_import_human_trace_rejects_wrong_schema():
    module = load_module()

    try:
        module.convert_trace({"schema_version": "human_trace_v1", "transitions": []})
    except ValueError as exc:
        assert "human_trace_v2" in str(exc)
    else:
        raise AssertionError("expected ValueError")
