from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_SOURCE = REPO_ROOT / "site" / "play" / "app.jsx"


def test_play_app_exports_research_trace_json():
    source = APP_SOURCE.read_text(encoding="utf-8")

    assert "buildHumanTrace" in source
    assert "downloadJson" in source
    assert "Export Trace JSON" in source
    assert "human_trace_" in source
    assert "schema_version: 'human_trace_v1'" in source
    assert "source: 'web_play'" in source


def test_trace_export_captures_observations_choices_and_terminal_state():
    source = APP_SOURCE.read_text(encoding="utf-8")

    assert "observation: stripClr(gameState.text || '')" in source
    assert "choices: choicesToTraceMap(choices)" in source
    assert "location_id: locationId" in source
    assert "params: paramsToTraceList(gameState.paramsState)" in source
    assert "terminal: {" in source
    assert "game_state: outcome" in source
    assert "traceSteps={traceSteps}" in source
    assert "setTraceSteps(prev => prev.slice(0, -1))" in source
