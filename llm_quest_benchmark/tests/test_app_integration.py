"""Integration tests for web application"""
import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime

from llm_quest_benchmark.web.app import create_app
from llm_quest_benchmark.constants import DEFAULT_TEMPLATE, DEFAULT_QUEST_TIMEOUT

@pytest.fixture
def app():
    """Create test Flask app"""
    # Create temp db file
    db_fd, db_path = tempfile.mkstemp()

    app = create_app({
        'TESTING': True,
        'DATABASE': Path(db_path),
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False
    })

    # Create test context
    with app.test_client() as client:
        with app.app_context():
            yield client

    # Clean up
    Path(db_path).unlink(missing_ok=True)

def test_main_app_smoke(app):
    """Basic smoke test for the main app"""
    response = app.get('/')
    assert response.status_code == 302  # Should redirect to monitor
    assert '/monitor' in response.location

def test_monitor_page(app):
    """Test monitor page loads"""
    response = app.get('/monitor/')
    assert response.status_code == 200
    assert b'Quest Runner' in response.data

def test_benchmark_page(app):
    """Test benchmark page loads"""
    response = app.get('/benchmark/')
    assert response.status_code == 200
    assert b'Benchmark Configuration' in response.data

def test_analyze_page(app):
    """Test analyze page loads"""
    response = app.get('/analyze/')
    assert response.status_code == 200
    assert b'Analysis' in response.data