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
    
    # Track all benchmark threads
    _threads = []
    
    @classmethod
    def terminate_all(cls):
        """Terminate all running benchmark threads"""
        logger.info(f"Terminating {len(cls._threads)} benchmark threads")
        # Just logging, actual termination happens via daemon=True
    
    def __init__(self, benchmark_id, config_dict, app):
        super().__init__()
        self.benchmark_id = benchmark_id
        self.config_dict = config_dict
        self.app = app
        # Set daemon so the thread won't block app shutdown
        self.daemon = True  
        # Add to thread tracking list
        BenchmarkThread._threads.append(self)
        
    def run(self):
        """Run benchmark thread"""
        try:
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
                                action_template=agent.get('template', 'reasoning.jinja'),
                                skip_single=agent.get('skip_single', True)
                            )
                            for agent in self.config_dict['agents']
                        ]
                    
                    # Create benchmark config with the benchmark_id
                    self.config_dict['benchmark_id'] = self.benchmark_id
                    benchmark_config = BenchmarkConfig(**self.config_dict)
                    
                    # Update status
                    status.update('running', 10, 'Preparing benchmark')
                    
                    # Create benchmark record with JSON-serializable config
                    serializable_config = self.config_dict.copy()
                    # Convert AgentConfig objects to dictionaries
                    if 'agents' in serializable_config:
                        serializable_config['agents'] = [
                            {
                                'model': agent.model,
                                'temperature': agent.temperature,
                                'system_template': agent.system_template,
                                'action_template': agent.action_template,
                                'skip_single': agent.skip_single,
                                'debug': agent.debug
                            }
                            for agent in serializable_config['agents']
                        ]
                    
                    benchmark_run = BenchmarkRun(
                        benchmark_id=self.benchmark_id,
                        name=self.config_dict.get('name', 'Benchmark'),
                        config=serializable_config,
                        status='running',
                        start_time=datetime.now()
                    )
                    
                    # Save to database
                    db.session.add(benchmark_run)
                    db.session.commit()
                    logger.info(f"Created benchmark record {benchmark_run.id}")
                    
                    # Update status
                    status.update('running', 20, 'Running benchmark')
                    
                    # Calculate total runs for progress tracking
                    total_quests = len(benchmark_config.quests)
                    total_agents = len(benchmark_config.agents)
                    total_runs = total_quests * total_agents
                    completed_runs = 0
                    
                    # Create a progress callback
                    def progress_callback(quest_name, agent_id):
                        nonlocal completed_runs
                        completed_runs += 1
                        progress = 20 + int((completed_runs / total_runs) * 70)  # Scale from 20% to 90%
                        status.update('running', progress, f'Running {quest_name} with {agent_id} ({completed_runs}/{total_runs})')
                    
                    # Override the renderer to use our progress tracking
                    benchmark_config.renderer = "null"  # Use minimal renderer since we track progress here
                    
                    # Run benchmark with progress tracking
                    results = core_run_benchmark(benchmark_config, progress_callback=progress_callback)
                    
                    # Update status
                    status.update('running', 90, 'Processing results')
                    
                    # Update database
                    benchmark_run = BenchmarkRun.query.filter_by(benchmark_id=self.benchmark_id).first()
                    if benchmark_run:
                        benchmark_run.status = 'complete'
                        benchmark_run.end_time = datetime.now()
                        
                        # Log results for debugging
                        logger.info(f"Storing benchmark results: {type(results)}, count: {len(results)}")
                        for i, result in enumerate(results[:3]):  # Log first 3 results for debugging
                            logger.info(f"Result {i}: {type(result)}, keys: {result.keys() if hasattr(result, 'keys') else 'N/A'}")
                        
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
        finally:
            # Cleanup - remove self from threads list
            if self in BenchmarkThread._threads:
                BenchmarkThread._threads.remove(self)