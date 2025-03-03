"""Database models for web interface"""
import json
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.types import TypeDecorator, TEXT
from llm_quest_benchmark.utils.choice_mapper import ChoiceMapper

db = SQLAlchemy()

class JSONEncodedDict(TypeDecorator):
    """Represents an immutable structure as a json-encoded string"""
    impl = TEXT

    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value)
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                # Try to repair damaged JSON
                try:
                    from json_repair import repair_json
                    repaired = repair_json(value)
                    return json.loads(repaired)
                except ImportError:
                    # Fallback if json-repair not available
                    import logging
                    logging.getLogger(__name__).warning("json-repair not available, returning raw value")
                    return value
        return None

class Run(db.Model):
    """Model for quest runs"""
    __tablename__ = 'runs'

    id = db.Column(db.Integer, primary_key=True)
    quest_name = db.Column(db.String(100), nullable=False)
    quest_file = db.Column(db.String(255), nullable=True)
    start_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    end_time = db.Column(db.DateTime)
    agent_id = db.Column(db.String(100), nullable=False)
    agent_config = db.Column(JSONEncodedDict, nullable=True)
    outcome = db.Column(db.String(50))
    reward = db.Column(db.Float, nullable=True)
    benchmark_id = db.Column(db.String(64), nullable=True)  # Link to benchmark run if part of one
    steps = db.relationship('Step', backref='run', lazy=True)

    def to_dict(self):
        """Convert run to dictionary"""
        return {
            'id': self.id,
            'quest_name': self.quest_name,
            'quest_file': self.quest_file,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'agent_id': self.agent_id,
            'agent_config': self.agent_config,
            'outcome': self.outcome,
            'reward': self.reward,
            'benchmark_id': self.benchmark_id
        }

class Step(db.Model):
    """Model for quest steps"""
    __tablename__ = 'steps'

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey('runs.id'), nullable=False)
    step = db.Column(db.Integer, nullable=False)
    location_id = db.Column(db.String(100), nullable=False)
    observation = db.Column(db.Text, nullable=False)
    choices = db.Column(JSONEncodedDict, nullable=True)
    action = db.Column(db.String(100))
    llm_response = db.Column(JSONEncodedDict, nullable=True)

    def to_dict(self):
        """Convert step to dictionary"""
        # Use ChoiceMapper to format choices with sequential numbers
        formatted_choices = []
        if self.choices:
            choice_mapper = ChoiceMapper(self.choices)
            formatted_choices = choice_mapper.get_numbered_choices()

        # Return fields in requested order: observation, choices, action, llm_response
        return {
            'observation': self.observation,
            'choices': formatted_choices,
            'action': self.action,
            'llm_response': self.llm_response,
            'location_id': self.location_id,
            'step': self.step,
            'id': self.id,
            'run_id': self.run_id
        }

class BenchmarkRun(db.Model):
    """Model for benchmark runs"""
    __tablename__ = 'benchmark_runs'

    id = db.Column(db.Integer, primary_key=True)
    benchmark_id = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(128))
    config = db.Column(JSONEncodedDict)  # Benchmark configuration
    status = db.Column(db.String(32), default='running')  # running, complete, error
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)
    results = db.Column(JSONEncodedDict, nullable=True)  # Benchmark results
    error = db.Column(db.Text, nullable=True)
    
    def to_dict(self):
        """Convert benchmark run to dictionary"""
        return {
            'id': self.id,
            'benchmark_id': self.benchmark_id,
            'name': self.name,
            'status': self.status,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'error': self.error
        }

def init_db(app):
    """Initialize database with application"""
    if 'SQLALCHEMY_DATABASE_URI' not in app.config:
        app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{app.config['DATABASE']}"
    if 'SQLALCHEMY_TRACK_MODIFICATIONS' not in app.config:
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    with app.app_context():
        db.create_all()