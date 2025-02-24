"""Database models for web interface"""
import json
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.types import TypeDecorator, TEXT

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
            return json.loads(value)
        return None

class Run(db.Model):
    """Model for quest runs"""
    __tablename__ = 'runs'

    id = db.Column(db.Integer, primary_key=True)
    quest_name = db.Column(db.String(100), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    end_time = db.Column(db.DateTime)
    agent_id = db.Column(db.String(100), nullable=False)
    agent_config = db.Column(JSONEncodedDict, nullable=True)
    outcome = db.Column(db.String(50))
    steps = db.relationship('Step', backref='run', lazy=True)

    def to_dict(self):
        """Convert run to dictionary"""
        return {
            'id': self.id,
            'quest_name': self.quest_name,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'agent_id': self.agent_id,
            'agent_config': self.agent_config,
            'outcome': self.outcome
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
        return {
            'id': self.id,
            'run_id': self.run_id,
            'step': self.step,
            'location_id': self.location_id,
            'observation': self.observation,
            'choices': self.choices,
            'action': self.action,
            'llm_response': self.llm_response
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