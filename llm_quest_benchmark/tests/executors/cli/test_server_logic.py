"""Tests for web server start logic."""
from unittest.mock import patch
import subprocess

from llm_quest_benchmark.executors.cli.logic.server_logic import start_server


@patch("llm_quest_benchmark.executors.cli.logic.server_logic.subprocess.run")
@patch("llm_quest_benchmark.web.init_db.init_database", return_value=True)
def test_start_server_production_mode(mock_init_db, mock_subprocess_run):
    success, message = start_server(
        host="127.0.0.1",
        port=8001,
        debug=False,
        workers=2,
        production=True,
    )

    assert success is True
    assert "127.0.0.1:8001" in message
    mock_subprocess_run.assert_called_once()
    cmd = mock_subprocess_run.call_args.args[0]
    assert cmd[0] == "gunicorn"
    assert "--workers" in cmd
    assert "2" in cmd


@patch(
    "llm_quest_benchmark.executors.cli.logic.server_logic.subprocess.run",
    side_effect=subprocess.CalledProcessError(1, ["gunicorn"]),
)
@patch("llm_quest_benchmark.web.init_db.init_database", return_value=True)
def test_start_server_production_mode_subprocess_error(mock_init_db, mock_subprocess_run):
    success, message = start_server(
        host="127.0.0.1",
        port=8001,
        debug=False,
        workers=2,
        production=True,
    )

    assert success is False
    assert "returned non-zero exit status 1" in message
