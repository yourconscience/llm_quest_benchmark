"""Tests for quest run analyzer"""
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typer.testing import CliRunner

from llm_quest_benchmark.executors.cli.commands import app
from llm_quest_benchmark.core.analyzer import analyze_quest_run, analyze_benchmark


def setup_test_db(db_path: Path):
    """Set up test database with sample data"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY,
            quest_name TEXT,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            model TEXT,
            template TEXT,
            outcome TEXT,
            reward REAL,
            benchmark_name TEXT
        )''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS steps (
            run_id INTEGER,
            step INTEGER,
            observation TEXT,
            choices TEXT,
            action INTEGER,
            reward REAL,
            llm_response TEXT,
            FOREIGN KEY(run_id) REFERENCES runs(id)
        )''')

    # Insert test data
    now = datetime.now()
    cursor.execute('''
        INSERT INTO runs (quest_name, start_time, end_time, model, template, outcome, reward, benchmark_name)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', ('test1.qm', now - timedelta(hours=1), now, 'test-model', 'test-template', 'SUCCESS', 1.0, 'baseline'))
    run1_id = cursor.lastrowid

    cursor.execute('''
        INSERT INTO runs (quest_name, start_time, end_time, model, template, outcome, reward, benchmark_name)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', ('test1.qm', now - timedelta(minutes=30), now, 'test-model', 'test-template', 'FAILURE', 0.0, 'baseline'))
    run2_id = cursor.lastrowid

    # Insert another run with different benchmark
    cursor.execute('''
        INSERT INTO runs (quest_name, start_time, end_time, model, template, outcome, reward, benchmark_name)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', ('test2.qm', now, now + timedelta(minutes=30), 'test-model', 'test-template', 'SUCCESS', 0.8, 'experimental'))
    run3_id = cursor.lastrowid

    # Insert steps for first run
    steps1 = [
        (run1_id, 1, "You are at a trading station.", json.dumps([{"id": "1", "text": "Talk to merchant"}, {"id": "2", "text": "Leave station"}]), 1, 0.0, '{"action": 1, "reasoning": "Should talk to merchant"}'),
        (run1_id, 2, "The merchant greets you.", json.dumps([{"id": "1", "text": "Buy"}, {"id": "2", "text": "Sell"}]), 2, 1.0, '{"action": 2, "reasoning": "Better to sell"}')
    ]
    cursor.executemany('''
        INSERT INTO steps (run_id, step, observation, choices, action, reward, llm_response)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', steps1)

    # Insert steps for second run
    steps2 = [
        (run2_id, 1, "You are at a trading station.", json.dumps([{"id": "1", "text": "Talk to merchant"}, {"id": "2", "text": "Leave station"}]), 2, 0.0, '{"action": 2, "reasoning": "Should leave"}')
    ]
    cursor.executemany('''
        INSERT INTO steps (run_id, step, observation, choices, action, reward, llm_response)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', steps2)

    conn.commit()
    conn.close()


def test_analyze_quest_run(tmp_path):
    """Test analyzing a specific quest run from database"""
    db_path = tmp_path / "metrics.db"
    setup_test_db(db_path)

    # Test CLI command
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["analyze", "--quest", "test1.qm", "--db", str(db_path), "--debug"])
        assert result.exit_code == 0

        # Check that summary info is present
        assert "Quest Run Summary" in result.stdout
        assert "test1.qm" in result.stdout
        assert "test-model" in result.stdout
        assert "test-template" in result.stdout
        assert "SUCCESS" in result.stdout
        assert "FAILURE" in result.stdout
        assert "Total Runs: 2" in result.stdout

        # Check that step info is present when debug is enabled
        assert "Step 1:" in result.stdout
        assert "Talk to merchant" in result.stdout
        assert "Leave station" in result.stdout
        assert "Step 2:" in result.stdout
        assert "Buy" in result.stdout
        assert "Sell" in result.stdout


def test_analyze_benchmark(tmp_path):
    """Test analyzing benchmark results from database"""
    db_path = tmp_path / "metrics.db"
    setup_test_db(db_path)

    # Test CLI command for all benchmarks
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["analyze", "--benchmark", "baseline", "--db", str(db_path)])
        assert result.exit_code == 0

        # Check that summary info is present
        assert "Benchmark Results" in result.stdout
        assert "Benchmark: baseline" in result.stdout
        assert "Total Runs: 2" in result.stdout
        assert "Success Rate: 50.0%" in result.stdout
        assert "Average Success Reward: 1.00" in result.stdout

        # Check that model stats are present
        assert "Model Performance" in result.stdout
        assert "test-model" in result.stdout
        assert "50.0%" in result.stdout

        # Check that quest stats are present
        assert "Quest Results" in result.stdout
        assert "test1.qm" in result.stdout


def test_analyze_specific_benchmark(tmp_path):
    """Test analyzing a specific benchmark from database"""
    db_path = tmp_path / "metrics.db"
    setup_test_db(db_path)

    # Test CLI command for specific benchmark
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["analyze", "--benchmark", "experimental", "--db", str(db_path)])
        assert result.exit_code == 0

        # Check that summary info is present
        assert "Benchmark Results" in result.stdout
        assert "Benchmark: experimental" in result.stdout
        assert "Total Runs: 1" in result.stdout
        assert "Success Rate: 100.0%" in result.stdout
        assert "Average Success Reward: 0.80" in result.stdout

        # Check that model stats are present
        assert "Model Performance" in result.stdout
        assert "test-model" in result.stdout
        assert "100.0%" in result.stdout

        # Check that quest stats are present
        assert "Quest Results" in result.stdout
        assert "test2.qm" in result.stdout


def test_analyze_metrics(tmp_path):
    """Test analyze command with a valid metrics file"""
    # Create test database
    db_path = tmp_path / "metrics.db"
    setup_test_db(db_path)

    # Test analyze_quest_run function
    results = analyze_quest_run("test1.qm", db_path)
    assert results["quest_name"] == "test1.qm"
    assert results["total_runs"] == 2
    assert results["outcomes"]["SUCCESS"] == 1
    assert results["outcomes"]["FAILURE"] == 1
    assert len(results["runs"]) == 2

    # Test CLI command
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["analyze", "--quest", "test1.qm", "--db", str(db_path)])
        assert result.exit_code == 0
        assert "Quest Run Summary" in result.stdout
        assert "test1.qm" in result.stdout
        assert "test-model" in result.stdout
        assert "test-template" in result.stdout
        assert "SUCCESS" in result.stdout
        assert "FAILURE" in result.stdout


def test_analyze_no_metrics_dir(tmp_path):
    """Test analyze command with non-existent metrics directory"""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["analyze", "--quest", "test1.qm"])
        assert result.exit_code == 1
        assert "Database not found" in result.stdout


def test_analyze_empty_metrics_dir(tmp_path):
    """Test analyze command with empty metrics directory"""
    # Create empty database
    db_path = tmp_path / "metrics.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY,
            quest_name TEXT,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            model TEXT,
            template TEXT,
            outcome TEXT,
            reward REAL,
            benchmark_name TEXT
        )''')
    conn.commit()
    conn.close()

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["analyze", "--quest", "test1.qm", "--db", str(db_path)])
        assert result.exit_code == 1
        assert "No runs found for quest" in result.stdout


def test_analyze_invalid_file(tmp_path):
    """Test analyze command with invalid database file"""
    # Create invalid database file
    db_path = tmp_path / "metrics.db"
    with open(db_path, "w") as f:
        f.write("invalid data")

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["analyze", "--quest", "test1.qm", "--db", str(db_path)])
        assert result.exit_code == 1
        assert "Error analyzing quest run" in result.stdout


def test_analyze_invalid_benchmark_file(tmp_path):
    """Test analyze command with invalid benchmark name"""
    # Create test database
    db_path = tmp_path / "metrics.db"
    setup_test_db(db_path)

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["analyze", "--benchmark", "nonexistent", "--db", str(db_path)])
        assert result.exit_code == 1
        assert "No benchmark data found for nonexistent" in result.stdout


def test_analyze_benchmark_directory(tmp_path):
    """Test analyze command with benchmark directory"""
    # Create test database with multiple benchmarks
    db_path = tmp_path / "metrics.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY,
            quest_name TEXT,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            model TEXT,
            template TEXT,
            outcome TEXT,
            reward REAL,
            benchmark_name TEXT
        )''')

    # Insert test data for multiple benchmarks
    now = datetime.now()
    test_data = [
        ('test1.qm', now, 'test-model', 'test-template', 'SUCCESS', 1.0, 'benchmark1'),
        ('test2.qm', now, 'test-model', 'test-template', 'FAILURE', 0.0, 'benchmark1'),
        ('test3.qm', now, 'test-model', 'test-template', 'SUCCESS', 0.5, 'benchmark2')
    ]

    for quest, time, model, template, outcome, reward, benchmark in test_data:
        cursor.execute('''
            INSERT INTO runs (quest_name, start_time, end_time, model, template, outcome, reward, benchmark_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (quest, time, time, model, template, outcome, reward, benchmark))

    conn.commit()
    conn.close()

    # Test CLI command
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["analyze", "--benchmark", "benchmark1", "--db", str(db_path)])
        assert result.exit_code == 0

        # Check that summary info is present
        assert "Benchmark Results" in result.stdout
        assert "Benchmark: benchmark1" in result.stdout
        assert "Total Runs: 2" in result.stdout
        assert "Success Rate: 50.0%" in result.stdout
        assert "Average Success Reward: 1.00" in result.stdout

        # Check that model stats are present
        assert "Model Performance" in result.stdout
        assert "test-model" in result.stdout
        assert "50.0%" in result.stdout

        # Check that quest stats are present
        assert "Quest Results" in result.stdout
        assert "test1.qm" in result.stdout
        assert "test2.qm" in result.stdout