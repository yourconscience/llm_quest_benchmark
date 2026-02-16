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
    events = db.relationship('RunEvent', backref='run', lazy=True)

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


class RunEvent(db.Model):
    """Structured runtime events for live monitor/debug views."""
    __tablename__ = 'run_events'

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey('runs.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    event_type = db.Column(db.String(32), nullable=False, index=True)  # step, timeout, outcome, error
    step = db.Column(db.Integer, nullable=True)
    location_id = db.Column(db.String(100), nullable=True)
    payload = db.Column(JSONEncodedDict, nullable=True)

    def to_dict(self):
        """Convert event to dictionary."""
        return {
            "id": self.id,
            "run_id": self.run_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "event_type": self.event_type,
            "step": self.step,
            "location_id": self.location_id,
            "payload": self.payload or {},
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

def import_benchmarks_from_file(app):
    """Import benchmarks from backup file"""
    import os
    import json
    import logging
    
    logger = logging.getLogger(__name__)
    backup_file = os.path.join(app.instance_path, 'benchmark_backup.json')
    
    if not os.path.exists(backup_file):
        logger.info(f"No benchmark backup file found at {backup_file}")
        return
    
    try:
        with open(backup_file, 'r') as f:
            benchmarks = json.load(f)
        
        with app.app_context():
            count = 0
            for benchmark_data in benchmarks:
                # Check if benchmark already exists
                existing = BenchmarkRun.query.filter_by(benchmark_id=benchmark_data['benchmark_id']).first()
                if not existing:
                    benchmark = BenchmarkRun(
                        benchmark_id=benchmark_data['benchmark_id'],
                        name=benchmark_data['name'],
                        config=benchmark_data['config'],
                        status=benchmark_data['status'],
                        start_time=datetime.fromisoformat(benchmark_data['start_time']) if benchmark_data['start_time'] else None,
                        end_time=datetime.fromisoformat(benchmark_data['end_time']) if benchmark_data['end_time'] else None,
                        results=benchmark_data['results'],
                        error=benchmark_data['error']
                    )
                    db.session.add(benchmark)
                    count += 1
            
            if count > 0:
                db.session.commit()
                logger.info(f"Imported {count} benchmarks from backup file")
    except Exception as e:
        logger.error(f"Error importing benchmarks from backup: {e}")


def export_benchmarks_to_file(app):
    """Export all benchmarks to backup file"""
    import os
    import json
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        with app.app_context():
            benchmarks = BenchmarkRun.query.all()
            if not benchmarks:
                logger.info("No benchmarks to export")
                return
            
            # Convert to JSON serializable format
            benchmark_data = []
            for benchmark in benchmarks:
                data = {
                    'id': benchmark.id,
                    'benchmark_id': benchmark.benchmark_id,
                    'name': benchmark.name,
                    'config': benchmark.config,
                    'status': benchmark.status,
                    'start_time': benchmark.start_time.isoformat() if benchmark.start_time else None,
                    'end_time': benchmark.end_time.isoformat() if benchmark.end_time else None,
                    'results': benchmark.results,
                    'error': benchmark.error
                }
                benchmark_data.append(data)
            
            # Ensure instance directory exists
            os.makedirs(app.instance_path, exist_ok=True)
            backup_file = os.path.join(app.instance_path, 'benchmark_backup.json')
            
            with open(backup_file, 'w') as f:
                json.dump(benchmark_data, f, indent=2)
            
            logger.info(f"Exported {len(benchmark_data)} benchmarks to {backup_file}")
    except Exception as e:
        logger.error(f"Error exporting benchmarks to backup: {e}")


def init_db(app):
    """Initialize database with application"""
    if 'SQLALCHEMY_DATABASE_URI' not in app.config:
        app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{app.config['DATABASE']}"
    if 'SQLALCHEMY_TRACK_MODIFICATIONS' not in app.config:
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    with app.app_context():
        db.create_all()
        
    # Import benchmarks from backup file if it exists
    import_benchmarks_from_file(app)
