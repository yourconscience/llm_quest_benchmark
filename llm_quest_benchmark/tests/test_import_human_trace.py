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


def test_import_human_trace_converts_to_run_summary(tmp_path):
    module = load_module()
    raw_trace = {
        "schema_version": "human_trace_v1",
        "source": "web_play",
        "quest_id": "Boat",
        "quest_title": "Boat",
        "quest_lang": "en",
        "started_at": "2026-05-21T12:00:00.000Z",
        "ended_at": "2026-05-21T12:01:00.000Z",
        "outcome": "SUCCESS",
        "steps": [
            {
                "step": 1,
                "location_id": 42,
                "observation": "You are at the dock.",
                "params": ["money: 10"],
                "choices": {"1": "Board the ship", "2": "Go home"},
                "human_decision": {
                    "choice_index": "1",
                    "choice_text": "Board the ship",
                    "jump_id": 7,
                },
            }
        ],
        "terminal": {"game_state": "win", "text": "Victory"},
    }
    input_path = tmp_path / "human_trace_Boat.json"
    output_path = tmp_path / "run_summary.json"
    input_path.write_text(json.dumps(raw_trace), encoding="utf-8")

    summary = module.convert_trace(raw_trace, source_trace=str(input_path))
    module.write_summary(summary, output_path)

    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert saved["quest_name"] == "Boat"
    assert saved["agent_id"] == "human_web"
    assert saved["agent_mode"] == "human"
    assert saved["outcome"] == "SUCCESS"
    assert saved["usage"]["total_tokens"] == 0
    assert saved["steps"][0]["observation"] == "You are at the dock."
    assert saved["steps"][0]["choices"] == {"1": "Board the ship", "2": "Go home"}
    assert saved["steps"][0]["llm_decision"]["choice"] == {"1": "Board the ship"}
    assert saved["steps"][0]["human_decision"]["jump_id"] == 7
    assert saved["terminal"]["text"] == "Victory"


def test_import_human_trace_rejects_wrong_schema():
    module = load_module()

    try:
        module.convert_trace({"schema_version": "other", "steps": []})
    except ValueError as exc:
        assert "human_trace_v1" in str(exc)
    else:
        raise AssertionError("expected ValueError")
