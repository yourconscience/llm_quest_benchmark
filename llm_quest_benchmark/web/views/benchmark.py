"""Benchmark configuration and execution blueprint"""
from flask import Blueprint, render_template, request, jsonify, current_app
import yaml
import json
import uuid
import threading
import time
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

from llm_quest_benchmark.executors.benchmark import run_benchmark
from ..models.database import db, Run, BenchmarkRun
from ..utils.errors import handle_errors, validate_quest_file, validate_model, WebUIError
from llm_quest_benchmark.schemas.config import BenchmarkConfig, AgentConfig, get_default_benchmark_yaml

bp = Blueprint('benchmark', __name__, url_prefix='/benchmark')

# Store active benchmarks in memory (in production, you'd use a persistent store)
active_benchmarks = {}

class InvalidConfigError(WebUIError):
    """Invalid benchmark configuration"""
    pass

def validate_benchmark_config(config):
    """Validate benchmark configuration"""
    try:
        config_dict = yaml.safe_load(config)

        # Check required fields
        if not isinstance(config_dict, dict):
            raise InvalidConfigError("Configuration must be a YAML dictionary")

        if 'quests' not in config_dict:
            raise InvalidConfigError("Configuration must specify 'quests' list")

        if not isinstance(config_dict['quests'], list):
            raise InvalidConfigError("'quests' must be a list")

        if not config_dict['quests']:
            raise InvalidConfigError("'quests' list cannot be empty")

        # Validate quest files exist
        for quest in config_dict['quests']:
            validate_quest_file(quest)

        # Validate agents if specified
        if 'agents' in config_dict:
            if not isinstance(config_dict['agents'], list):
                raise InvalidConfigError("'agents' must be a list")

            for agent in config_dict['agents']:
                if not isinstance(agent, dict):
                    raise InvalidConfigError("Each agent must be a dictionary")
                if 'model' not in agent:
                    raise InvalidConfigError("Each agent must specify a 'model'")
                validate_model(agent['model'])

        return config_dict

    except yaml.YAMLError as e:
        raise InvalidConfigError(f"Invalid YAML format: {str(e)}")

# Use the default config from schemas module
DEFAULT_CONFIG = get_default_benchmark_yaml()

@bp.route('/')
@handle_errors
def index():
    """Benchmark configuration page"""
    return render_template('benchmark/index.html',
                         default_config=DEFAULT_CONFIG)

class BenchmarkStatus:
    """Benchmark status tracker"""
    def __init__(self, benchmark_id, config_dict):
        self.benchmark_id = benchmark_id
        self.config_dict = config_dict
        self.status = 'initializing'
        self.progress = 0
        self.current_task = 'Starting benchmark'
        self.start_time = datetime.now()
        self.end_time = None
        self.result = None
        self.error = None
        
    def update(self, status, progress, current_task=None):
        self.status = status
        self.progress = progress
        if current_task:
            self.current_task = current_task
            
    def complete(self, result):
        self.status = 'complete'
        self.progress = 100
        self.current_task = 'Benchmark complete'
        self.end_time = datetime.now()
        self.result = result
        
    def failed(self, error):
        self.status = 'error'
        self.current_task = f'Error: {error}'
        self.end_time = datetime.now()
        self.error = str(error)
        
    def to_dict(self):
        return {
            'benchmark_id': self.benchmark_id,
            'status': self.status,
            'progress': self.progress,
            'current_task': self.current_task,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'error': self.error
        }

def run_benchmark_thread(benchmark_id, config_dict, app=None):
    """Run benchmark in a background thread
    
    Args:
        benchmark_id: Unique ID for the benchmark
        config_dict: Configuration dictionary
        app: Flask application instance to use for context
    """
    benchmark_status = active_benchmarks.get(benchmark_id)
    if not benchmark_status:
        logger.error(f"Benchmark {benchmark_id} not found")
        return
    
    # Create a new app context that will be used for all database operations
    if app is None:
        logger.error("No Flask app provided to thread")
        benchmark_status.failed("No Flask app context available")
        return
        
    app_context = app.app_context()
    app_context.push()  # Push application context at thread start
    
    try:
        # Convert agent dictionaries to AgentConfig objects
        if 'agents' in config_dict:
            config_dict['agents'] = [
                AgentConfig(
                    model=agent['model'],
                    temperature=agent.get('temperature', 0.0),
                    system_template=agent.get('template', 'reasoning.jinja'),
                    skip_single=agent.get('skip_single', True)
                )
                for agent in config_dict['agents']
            ]
        
        # Create benchmark config
        benchmark_config = BenchmarkConfig(**config_dict)
        
        # Update status
        benchmark_status.update('running', 10, 'Preparing benchmark')
        
        # Create benchmark run record
        benchmark_run = BenchmarkRun(
            benchmark_id=benchmark_id,
            name=config_dict.get('name', 'Benchmark'),
            config=config_dict,
            status='running',
            start_time=datetime.now()
        )
        
        # Store benchmark record - now using the thread's own app context
        db.session.add(benchmark_run)
        db.session.commit()
        
        # Update status
        benchmark_status.update('running', 20, 'Starting quest runs')
        
        # Run benchmark
        results = run_benchmark(benchmark_config)
        
        # Update status
        benchmark_status.update('running', 90, 'Processing results')
        
        # Update database record - now using the thread's own app context
        benchmark_run = BenchmarkRun.query.filter_by(benchmark_id=benchmark_id).first()
        if benchmark_run:
            benchmark_run.status = 'complete'
            benchmark_run.end_time = datetime.now()
            benchmark_run.results = results
            db.session.commit()
        
        # Complete status
        benchmark_status.complete(results)
        
    except Exception as e:
        logger.error(f"Error running benchmark {benchmark_id}: {str(e)}", exc_info=True)
        benchmark_status.failed(str(e))
        
        # Update database record - now using the thread's own app context
        try:
            benchmark_run = BenchmarkRun.query.filter_by(benchmark_id=benchmark_id).first()
            if benchmark_run:
                benchmark_run.status = 'error'
                benchmark_run.end_time = datetime.now()
                benchmark_run.error = str(e)
                db.session.commit()
        except Exception as db_error:
            logger.error(f"Error updating benchmark status in DB: {db_error}")
    
    finally:
        # Always pop the app context at the end of the thread
        app_context.pop()

@bp.route('/run', methods=['POST'])
@handle_errors
def run():
    """Run benchmark with given configuration"""
    if not request.is_json:
        return jsonify({'success': False, 'error': 'Request must be JSON'}), 400

    data = request.get_json()
    if 'config' not in data:
        return jsonify({'success': False, 'error': 'Missing config field'}), 400

    try:
        config_dict = validate_benchmark_config(data['config'])
        
        # Generate unique benchmark ID
        benchmark_id = str(uuid.uuid4())
        
        # Create benchmark status tracker
        benchmark_status = BenchmarkStatus(benchmark_id, config_dict)
        active_benchmarks[benchmark_id] = benchmark_status
        
        # Get current Flask app for the thread
        flask_app = current_app._get_current_object()  # Get the actual app instance
        
        # Start benchmark in background thread with app context
        thread = threading.Thread(
            target=run_benchmark_thread,
            args=(benchmark_id, config_dict, flask_app)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Benchmark started successfully',
            'benchmark_id': benchmark_id
        })

    except Exception as e:
        logger.error(f"Failed to run benchmark: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/status/<benchmark_id>')
@handle_errors
def status(benchmark_id):
    """Get benchmark status"""
    # First check active benchmarks in memory
    benchmark_status = active_benchmarks.get(benchmark_id)
    if benchmark_status:
        return jsonify({
            'success': True,
            'benchmark_id': benchmark_id,
            'status': benchmark_status.status,
            'progress': benchmark_status.progress,
            'current_task': benchmark_status.current_task
        })
    
    # If not in memory, check database for completed benchmark
    benchmark_run = BenchmarkRun.query.filter_by(benchmark_id=benchmark_id).first()
    if benchmark_run:
        return jsonify({
            'success': True,
            'benchmark_id': benchmark_id,
            'status': benchmark_run.status,
            'progress': 100 if benchmark_run.status == 'complete' else 0,
            'current_task': 'Complete' if benchmark_run.status == 'complete' else benchmark_run.error or 'Unknown'
        })
    
    return jsonify({
        'success': False,
        'error': f'Benchmark {benchmark_id} not found'
    }), 404

@bp.route('/results')
@handle_errors
def results():
    """Get benchmark results"""
    # Get recent benchmark runs from database
    benchmark_runs = BenchmarkRun.query.order_by(BenchmarkRun.start_time.desc()).limit(10).all()
    
    # Format results
    results = []
    for run in benchmark_runs:
        results.append({
            'id': run.id,
            'benchmark_id': run.benchmark_id,
            'name': run.name,
            'status': run.status,
            'timestamp': run.start_time.isoformat(),
            'end_time': run.end_time.isoformat() if run.end_time else None
        })
    
    # Add active benchmarks not yet in database
    for benchmark_id, status in active_benchmarks.items():
        if status.status != 'complete' and not any(r['benchmark_id'] == benchmark_id for r in results):
            results.append({
                'id': None,
                'benchmark_id': benchmark_id,
                'name': status.config_dict.get('name', 'Running Benchmark'),
                'status': status.status,
                'timestamp': status.start_time.isoformat(),
                'end_time': None
            })
    
    return jsonify({
        'success': True,
        'results': results
    })