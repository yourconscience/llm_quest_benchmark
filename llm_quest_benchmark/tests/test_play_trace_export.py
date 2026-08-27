from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_SOURCE = REPO_ROOT / "site" / "play" / "app.jsx"


def test_play_app_exports_research_trace_json():
    source = APP_SOURCE.read_text(encoding="utf-8")

    assert "buildHumanTrace" in source
    assert "downloadJson" in source
    assert "Export Trace JSON" in source
    assert "human_trace_" in source
    assert "schema_version: 'human_trace_v2'" in source
    assert "source: 'web_play'" in source


def test_trace_export_captures_snapshots_choices_and_terminal_state():
    source = APP_SOURCE.read_text(encoding="utf-8")

    assert "function traceSnapshot(" in source
    assert "observation: stripClr(state.text || '')" in source
    assert "choices: choicesToTraceMap(activeChoices)" in source
    assert "params: paramsToTraceList(state.paramsState)" in source
    assert "saving: player.getSaving()" in source
    assert "terminal: {" in source
    assert "game_state: outcome" in source
    assert "traceTransitions={traceTransitions}" in source


def test_trace_export_retains_restore_events_instead_of_erasing_them():
    """Backtracking in the web player truncates only the active branch; the
    exported trace keeps every executed transition, including the restore."""
    source = APP_SOURCE.read_text(encoding="utf-8")

    assert "kind: 'restore'" in source
    assert "checkpoint_index: checkpointIndex" in source
    # The old export truncated undone steps out of the trace.
    assert "setTraceSteps(prev => prev.slice(0, -1))" not in source
    assert "setTraceTransitions(prev => prev.slice(0, -1))" not in source
    # Undo still truncates the active checkpoint branch and the UI decision path.
    assert "setStepHistory(prev => prev.slice(0, -1))" in source
    assert "setPath(prev => prev.slice(0, -1))" in source
