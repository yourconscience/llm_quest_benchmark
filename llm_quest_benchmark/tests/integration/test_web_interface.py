"""Tests for web interface"""
import pytest
from llm_quest_benchmark.web.app import create_app
from llm_quest_benchmark.constants import DEFAULT_QUEST

@pytest.fixture
def app():
    """Create test Flask app"""
    app = create_app()
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'DEFAULT_QUEST': str(DEFAULT_QUEST)
    })
    return app

@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()

def test_index_redirect(client):
    """Test index redirects to monitor page"""
    response = client.get('/')
    assert response.status_code == 302
    assert response.location == '/monitor'

def test_monitor_page(client):
    """Test monitor page loads"""
    response = client.get('/monitor')
    assert response.status_code == 200
    assert b'Quest Monitor' in response.data

def test_benchmark_page(client):
    """Test benchmark page loads"""
    response = client.get('/benchmark')
    assert response.status_code == 200
    assert b'Quest Benchmark' in response.data

def test_analyze_page(client):
    """Test analyze page loads"""
    response = client.get('/analyze')
    assert response.status_code == 200
    assert b'Quest Analysis' in response.data

def test_run_quest_basic(client):
    """Test basic quest run"""
    data = {
        'quest_file': str(DEFAULT_QUEST),
        'model': 'gpt-4',
        'temperature': 0.7
    }
    response = client.post('/monitor/run', json=data)
    assert response.status_code == 200
    assert 'run_id' in response.json

def test_run_quest_invalid_model(client):
    """Test quest run with invalid model"""
    data = {
        'quest_file': str(DEFAULT_QUEST),
        'model': 'invalid-model',
        'temperature': 0.7
    }
    response = client.post('/monitor/run', json=data)
    assert response.status_code == 400
    assert 'error' in response.json

def test_run_quest_missing_file(client):
    """Test quest run with missing file"""
    data = {
        'quest_file': 'nonexistent.qm',
        'model': 'gpt-4',
        'temperature': 0.7
    }
    response = client.post('/monitor/run', json=data)
    assert response.status_code == 400
    assert 'error' in response.json