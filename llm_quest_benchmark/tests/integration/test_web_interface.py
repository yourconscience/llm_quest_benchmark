"""Tests for web interface"""
import pytest
from llm_quest_benchmark.web.app import create_app
from llm_quest_benchmark.web.models.database import db, Run, Step
from llm_quest_benchmark.constants import DEFAULT_QUEST
import json

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

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

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
    assert b'Quest Runner' in response.data

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

def test_quest_initialization(client, app):
    """Test quest initialization"""
    with app.app_context():
        # Test quest initialization
        data = {
            'quest': 'kr1/Boat.qm',
            'model': 'random_choice',
            'temperature': 0.7,
            'template': 'reasoning'
        }
        response = client.post('/monitor/run', json=data)
        assert response.status_code == 200
        assert response.json['success']
        assert 'run_id' in response.json
        assert 'state' in response.json

        # Verify initial state
        state = response.json['state']
        assert state['step'] == 1
        assert 'location_id' in state
        assert 'observation' in state
        assert 'choices' in state
        assert isinstance(state['choices'], list)
        assert not state['game_ended']

        # Verify database entry
        run = Run.query.get(response.json['run_id'])
        assert run is not None
        assert run.quest_name == 'kr1/Boat.qm'
        assert run.agent_id == 'random_choice'
        assert not run.end_time

def test_quest_step(client, app):
    """Test taking a step in a quest"""
    with app.app_context():
        # Initialize quest
        init_data = {
        'quest': 'kr1/Boat.qm',
            'model': 'random_choice',
            'temperature': 0.7,
            'template': 'reasoning'
    }
        init_response = client.post('/monitor/run', json=init_data)
        assert init_response.status_code == 200
        run_id = init_response.json['run_id']

        # Take a step
        step_data = {'choice': 1}
        step_response = client.post(f'/monitor/step/{run_id}', json=step_data)
        assert step_response.status_code == 200
        assert step_response.json['success']

        # Verify step state
        state = step_response.json['state']
        assert state['step'] == 2
        assert 'location_id' in state
        assert 'observation' in state
        assert 'choices' in state
        assert isinstance(state['choices'], list)

def test_quest_invalid_step(client, app):
    """Test invalid step handling"""
    with app.app_context():
        # Initialize quest
        init_data = {
            'quest': 'kr1/Boat.qm',
        'model': 'random_choice',
            'temperature': 0.7,
            'template': 'reasoning'
    }
        init_response = client.post('/monitor/run', json=init_data)
        assert init_response.status_code == 200
        run_id = init_response.json['run_id']

        # Test invalid choice
        step_data = {'choice': 999}  # Invalid choice number
        step_response = client.post(f'/monitor/step/{run_id}', json=step_data)
        assert step_response.status_code == 400
        assert 'error' in step_response.json

        # Test missing choice
        step_response = client.post(f'/monitor/step/{run_id}', json={})
        assert step_response.status_code == 400
        assert 'error' in step_response.json
        assert 'No choice provided' in step_response.json['error']

def test_database_operations(app):
    """Test database operations"""
    with app.app_context():
        # Create a test run
        run = Run(
            quest_name='test_quest',
            agent_id='test_agent',
            agent_config={'model': 'random_choice'}
        )
        db.session.add(run)
        db.session.commit()

        # Add a step
        step = Step(
            run_id=run.id,
            step=1,
            location_id='start',
            observation='Test observation',
            choices=json.dumps([{'id': '1', 'text': 'choice1'}, {'id': '2', 'text': 'choice2'}]),
            action='1'
        )
        db.session.add(step)
        db.session.commit()

        # Verify data
        saved_run = Run.query.first()
        assert saved_run.quest_name == 'test_quest'
        assert saved_run.agent_id == 'test_agent'
        assert saved_run.agent_config == {'model': 'random_choice'}

        saved_step = Step.query.first()
        assert saved_step.run_id == run.id
        assert saved_step.step == 1
        assert saved_step.location_id == 'start'
        assert len(json.loads(saved_step.choices)) == 2