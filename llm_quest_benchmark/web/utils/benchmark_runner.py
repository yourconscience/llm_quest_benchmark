"""Benchmark thread runner for web interface"""
import logging
import threading
import uuid
from datetime import datetime
from typing import Dict, Any, List

from flask import Flask
from llm_quest_benchmark.schemas.config import BenchmarkConfig, AgentConfig
from llm_quest_benchmark.executors.benchmark import run_benchmark as core_run_benchmark
from ..models.database import db, BenchmarkRun

logger = logging.getLogger(__name__)

# Store active benchmarks in memory
active_benchmarks = {}

class BenchmarkStatus:
    """Track benchmark status"""
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

def get_benchmark_status(benchmark_id):
    """Get status of a benchmark"""
    return active_benchmarks.get(benchmark_id)

def list_active_benchmarks():
    """Get list of active benchmarks"""
    return {k: v.to_dict() for k, v in active_benchmarks.items()}

def start_benchmark(config_dict: Dict[str, Any], app: Flask):
    """Start a benchmark in a background thread
    
    Args:
        config_dict: Benchmark configuration
        app: Flask application
        
    Returns:
        benchmark_id: ID of the benchmark
    """
    # Generate benchmark ID
    benchmark_id = str(uuid.uuid4())
    
    # Create status tracker
    status = BenchmarkStatus(benchmark_id, config_dict)
    active_benchmarks[benchmark_id] = status
    
    # Create thread
    thread = BenchmarkThread(
        benchmark_id=benchmark_id,
        config_dict=config_dict,
        app=app
    )
    thread.start()
    
    return benchmark_id

class BenchmarkThread(threading.Thread):
    """Thread for running benchmarks"""
    
    def __init__(self, benchmark_id, config_dict, app):
        super().__init__()
        self.benchmark_id = benchmark_id
        self.config_dict = config_dict
        self.app = app
        self.daemon = True  # Make thread a daemon so it exits when main program exits
        
    def run(self):
        """Run benchmark thread"""
        # Get status tracker
        status = active_benchmarks.get(self.benchmark_id)
        if not status:
            logger.error(f"No status tracker for benchmark {self.benchmark_id}")
            return
        
        # Set up app context for this thread
        with self.app.app_context():
            try:
                # Convert agent dictionaries to AgentConfig objects
                if 'agents' in self.config_dict:
                    self.config_dict['agents'] = [
                        AgentConfig(
                            model=agent['model'],
                            temperature=agent.get('temperature', 0.0),
                            system_template=agent.get('template', 'reasoning.jinja'),
                            skip_single=agent.get('skip_single', True)
                        )
                        for agent in self.config_dict['agents']
                    ]
                
                # Create benchmark config
                benchmark_config = BenchmarkConfig(**self.config_dict)
                
                # Update status
                status.update('running', 10, 'Preparing benchmark')
                
                # Create benchmark record
                benchmark_run = BenchmarkRun(
                    benchmark_id=self.benchmark_id,
                    name=self.config_dict.get('name', 'Benchmark'),
                    config=self.config_dict,
                    status='running',
                    start_time=datetime.now()
                )
                
                # Save to database
                db.session.add(benchmark_run)
                db.session.commit()
                logger.info(f"Created benchmark record {benchmark_run.id}")
                
                # Update status
                status.update('running', 20, 'Running benchmark')
                
                # Run benchmark
                results = core_run_benchmark(benchmark_config)
                
                # Update status
                status.update('running', 90, 'Processing results')
                
                # Update database
                benchmark_run = BenchmarkRun.query.filter_by(benchmark_id=self.benchmark_id).first()
                if benchmark_run:
                    benchmark_run.status = 'complete'
                    benchmark_run.end_time = datetime.now()
                    benchmark_run.results = results
                    db.session.commit()
                    logger.info(f"Updated benchmark record {benchmark_run.id}")
                
                # Complete status
                status.complete(results)
                
            except Exception as e:
                logger.error(f"Error running benchmark {self.benchmark_id}: {e}", exc_info=True)
                status.failed(str(e))
                
                # Update database
                try:
                    benchmark_run = BenchmarkRun.query.filter_by(benchmark_id=self.benchmark_id).first()
                    if benchmark_run:
                        benchmark_run.status = 'error'
                        benchmark_run.end_time = datetime.now()
                        benchmark_run.error = str(e)
                        db.session.commit()
                        logger.info(f"Updated benchmark record with error {benchmark_run.id}")
                except Exception as db_e:
                    logger.error(f"Error updating benchmark record: {db_e}")