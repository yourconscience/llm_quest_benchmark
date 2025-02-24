"""Tests for Flask application"""
import pytest
from llm_quest_benchmark.web.app import create_app
from llm_quest_benchmark.web.models.database import db
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

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()

def test_main_app_smoke(client):
    """Test main app routes"""
    # Test index redirect
    response = client.get('/')
    assert response.status_code == 302
    assert response.location == '/monitor'

    # Test monitor page
    response = client.get('/monitor')
    assert response.status_code == 200
    assert b'Quest Monitor' in response.data

    # Test benchmark page
    response = client.get('/benchmark')
    assert response.status_code == 200
    assert b'Quest Benchmark' in response.data

    # Test analyze page
    response = client.get('/analyze')
    assert response.status_code == 200
    assert b'Quest Analysis' in response.data

def test_database_operations(app):
    """Test basic database operations"""
    from llm_quest_benchmark.web.models.database import Run, Step

    with app.app_context():
        # Create a test run
        run = Run(
            quest_name='test_quest',
            agent_id='test_agent',
            agent_config={'model': 'gpt-4'}
        )
        db.session.add(run)
        db.session.commit()

        # Add a step
        step = Step(
            run_id=run.id,
            step=1,
            location_id='start',
            observation='Test observation',
            choices=['choice1', 'choice2'],
            action='choice1'
        )
        db.session.add(step)
        db.session.commit()

        # Verify data
        saved_run = Run.query.first()
        assert saved_run.quest_name == 'test_quest'
        assert saved_run.agent_id == 'test_agent'
        assert saved_run.agent_config == {'model': 'gpt-4'}

        saved_step = Step.query.first()
        assert saved_step.run_id == run.id
        assert saved_step.step == 1
        assert saved_step.location_id == 'start'
        assert saved_step.choices == ['choice1', 'choice2']
