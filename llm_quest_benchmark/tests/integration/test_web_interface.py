"""Integration tests for web interface"""
import pytest
from pathlib import Path
import json
import tempfile
import yaml

from llm_quest_benchmark.web.app import create_app
from llm_quest_benchmark.constants import DEFAULT_QUEST, DEFAULT_MODEL, DEFAULT_TEMPLATE

@pytest.fixture
def app():
    """Create test Flask app"""
    # Create temp db file
    db_fd, db_path = tempfile.mkstemp()
    db_uri = f'sqlite:///{db_path}'

    app = create_app({
        'TESTING': True,
        'DATABASE': Path(db_path),
        'SQLALCHEMY_DATABASE_URI': db_uri,
        'SQLALCHEMY_TRACK_MODIFICATIONS': False
    })

    # Initialize database
    with app.app_context():
        from llm_quest_benchmark.web.models.database import db
        db.create_all()

    yield app

    # Clean up
    with app.app_context():
        db.drop_all()
    Path(db_path).unlink(missing_ok=True)

@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()

@pytest.fixture
def example_quest_path(tmp_path):
    """Create a test quest file"""
    # Create quests directory
    quests_dir = Path("quests")
    quests_dir.mkdir(exist_ok=True)

    # Create quest file
    quest_path = quests_dir / "boat.qm"
    quest_path.write_text("""
    [start]
    text: You are in a boat.
    choices:
        - Go north: end_success

    [end_success]
    text: You made it!
    success: true
    """)
    return str(quest_path)

def test_index_redirect(client):
    """Test index redirects to monitor"""
    response = client.get('/')
    assert response.status_code == 302
    assert 'monitor' in response.location

def test_monitor_page(client):
    """Test monitor page loads"""
    response = client.get('/monitor/')
    assert response.status_code == 200
    assert b'Quest Runner' in response.data

def test_benchmark_page(client):
    """Test benchmark page loads"""
    response = client.get('/benchmark/')
    assert response.status_code == 200
    assert b'Benchmark Configuration' in response.data

def test_analyze_page(client):
    """Test analyze page loads"""
    response = client.get('/analyze/')
    assert response.status_code == 200
    assert b'Analysis' in response.data

@pytest.mark.timeout(5)
def test_run_quest_basic(app, client, example_quest_path):
    """Test basic quest run through web interface"""
    with app.app_context():
        response = client.post('/monitor/run',
                          data=json.dumps({
                              'quest': 'boat.qm',
                              'agent': {
                                  'model': 'random_choice',  # Use random_choice agent for testing
                                  'temperature': 0.0,
                                  'template': DEFAULT_TEMPLATE,
                                  'agent_id': 'test_agent'
                              }
                          }),
                          content_type='application/json')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True

def test_run_quest_invalid_model(client, example_quest_path):
    """Test quest run with invalid model"""
    data = {
        'quest': 'boat.qm',
        'agent': {
            'model': 'invalid_model',
            'temperature': 0.0,
            'template': DEFAULT_TEMPLATE,
            'agent_id': 'test_agent'
        }
    }

    response = client.post('/monitor/run',
                       data=json.dumps(data),
                       content_type='application/json')

    assert response.status_code == 400
    result = json.loads(response.data)
    assert not result['success']
    assert 'Invalid model' in result['error']

def test_run_quest_missing_file(client):
    """Test quest run with missing file"""
    data = {
        'quest': 'nonexistent.qm',
        'agent': {
            'model': DEFAULT_MODEL,
            'temperature': 0.0,
            'template': DEFAULT_TEMPLATE,
            'agent_id': 'test_agent'
        }
    }

    response = client.post('/monitor/run',
                       data=json.dumps(data),
                       content_type='application/json')

    assert response.status_code == 400
    result = json.loads(response.data)
    assert not result['success']
    assert 'Quest file not found' in result['error']

@pytest.mark.timeout(5)
def test_benchmark_run_basic(app, client, example_quest_path):
    """Test basic benchmark run through web interface"""
    with app.app_context():
        config = {
            'quests': [example_quest_path],
            'agents': [{
                'model': 'random_choice',  # Use random_choice agent for testing
                'temperature': 0.0,
                'template': DEFAULT_TEMPLATE,
                'skip_single': True
            }],
            'quest_timeout': 2,  # Short timeout for testing
            'max_workers': 1,
            'debug': True
        }

        response = client.post('/benchmark/run',
                          data=json.dumps({'config': yaml.dump(config)}),
                          content_type='application/json')

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True

def test_analyze_no_data(app, client):
    """Test analysis endpoints with no data"""
    with app.app_context():
        # Clear any existing data
        from llm_quest_benchmark.web.models.database import db
        db.drop_all()
        db.create_all()

        endpoints = ['/analyze/summary', '/analyze/model_comparison', '/analyze/step_analysis']

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 400
            result = json.loads(response.data)
            assert not result['success']
            assert 'No data available' in result['error']