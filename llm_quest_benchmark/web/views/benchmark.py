"""Benchmark configuration and execution blueprint"""
from flask import Blueprint, render_template, request, jsonify
import yaml
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

from llm_quest_benchmark.executors.benchmark import run_benchmark
from ..models.database import db, Run
from ..utils.errors import handle_errors, validate_quest_file, validate_model, WebUIError
from llm_quest_benchmark.schemas.config import BenchmarkConfig, AgentConfig

bp = Blueprint('benchmark', __name__, url_prefix='/benchmark')

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

DEFAULT_CONFIG = """# Main LLM benchmark configuration
quests:
  - quests/boat.qm  # Example quest path
agents:
  - model: random_choice
    skip_single: true
    temperature: 0.5
    template: reasoning.jinja
debug: false
quest_timeout: 30
max_workers: 1"""

@bp.route('/')
@handle_errors
def index():
    """Benchmark configuration page"""
    return render_template('benchmark/index.html',
                         default_config=DEFAULT_CONFIG)

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

        benchmark_config = BenchmarkConfig(**config_dict)
        run_benchmark(benchmark_config)

        return jsonify({
            'success': True,
            'message': 'Benchmark started successfully'
        })

    except Exception as e:
        logger.error(f"Failed to run benchmark: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/results')
@handle_errors
def results():
    """Get benchmark results"""
    runs = Run.query.order_by(Run.start_time.desc()).all()
    return jsonify({
        'success': True,
        'runs': [run.to_dict() for run in runs]
    })