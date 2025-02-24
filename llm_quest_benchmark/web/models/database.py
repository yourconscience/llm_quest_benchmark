"""Database models for the web application"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class Run(db.Model):
    """Quest run model"""
    __tablename__ = 'runs'

    id = db.Column(db.Integer, primary_key=True)
    quest_name = db.Column(db.String, nullable=False)
    start_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    end_time = db.Column(db.DateTime)
    agent_id = db.Column(db.String)  # Added agent_id field
    agent_config = db.Column(db.Text)  # JSON string of agent configuration
    outcome = db.Column(db.String)  # SUCCESS, FAILURE, ERROR, etc.

    # Relationship with steps
    steps = db.relationship('Step', backref='run', lazy=True)

    def to_dict(self):
        """Convert run to dictionary"""
        return {
            'id': self.id,
            'quest_name': self.quest_name,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'agent_id': self.agent_id,
            'agent_config': json.loads(self.agent_config) if self.agent_config else None,
            'outcome': self.outcome
        }

class Step(db.Model):
    """Quest step model"""
    __tablename__ = 'steps'

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey('runs.id'), nullable=False)
    step = db.Column(db.Integer, nullable=False)
    location_id = db.Column(db.String, nullable=False)
    observation = db.Column(db.Text, nullable=False)
    choices = db.Column(db.Text)  # JSON array of choice objects
    action = db.Column(db.String)
    llm_response = db.Column(db.Text)  # JSON object of LLMResponse

    def to_dict(self):
        """Convert step to dictionary"""
        return {
            'id': self.id,
            'run_id': self.run_id,
            'step': self.step,
            'location_id': self.location_id,
            'observation': self.observation,
            'choices': json.loads(self.choices) if self.choices else None,
            'action': self.action,
            'llm_response': json.loads(self.llm_response) if self.llm_response else None
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