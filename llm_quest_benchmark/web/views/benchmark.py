"""Benchmark configuration and execution blueprint"""
import json
import logging
from datetime import datetime
from pathlib import Path

import yaml
from flask import Blueprint, current_app, jsonify, render_template, request

logger = logging.getLogger(__name__)

from llm_quest_benchmark.agents.agent_manager import AgentManager
from llm_quest_benchmark.schemas.config import (
    AgentConfig,
    BenchmarkConfig,
    get_default_benchmark_yaml,
)

from ..models.database import BenchmarkRun, Run, db
from ..utils.benchmark_runner import get_benchmark_status, list_active_benchmarks, start_benchmark
from ..utils.errors import WebUIError, handle_errors, validate_model, validate_quest_file
# Import the agent management code from monitor
from .monitor import get_available_agents

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

            # Get list of valid agent IDs
            agent_manager = AgentManager()
            valid_agent_ids = set(agent_manager.list_agents())

            # Check if we have a mixture of strings and dictionaries (old format)
            has_dict_agents = any(isinstance(a, dict) for a in config_dict['agents'])
            has_string_agents = any(isinstance(a, str) for a in config_dict['agents'])

            if has_dict_agents:
                # For backward compatibility, we'll process the old format
                # but warn it's deprecated
                if has_string_agents:
                    raise InvalidConfigError(
                        "Mixed agent types: configuration cannot contain both agent IDs and dictionaries. "
                        "Use only agent IDs (strings).")

                # Convert the old format to agent IDs on the fly
                new_agent_ids = []
                for agent in config_dict['agents']:
                    if not isinstance(agent, dict):
                        raise InvalidConfigError(
                            "Each agent must be a string (agent ID) or dictionary (old format)")

                    # Handle saved agents vs. direct model specification
                    if 'agent_id' in agent:
                        # Use the specified agent ID
                        agent_id = agent['agent_id']
                        if agent_id not in valid_agent_ids:
                            raise InvalidConfigError(f"Unknown agent ID: {agent_id}")
                        new_agent_ids.append(agent_id)
                    elif 'model' in agent:
                        # Create a temporary agent from model specification
                        validate_model(agent['model'])

                        # Handle 'template' key which maps to action_template in AgentConfig
                        if 'template' in agent:
                            agent['action_template'] = agent.pop('template')

                        # Create a temporary agent config
                        agent_config = AgentConfig(**agent)
                        agent_id = agent_config.generated_agent_id

                        # Create the agent if it doesn't exist
                        if agent_id not in valid_agent_ids:
                            agent_config.agent_id = agent_id  # Set the ID explicitly
                            agent_manager.create_agent(agent_config)

                        new_agent_ids.append(agent_id)
                    else:
                        raise InvalidConfigError(
                            "Each agent must specify either 'agent_id' or 'model'")

                # Replace the agents list with the new agent IDs
                config_dict['agents'] = new_agent_ids
            else:
                # Validate all agent IDs exist
                for agent_id in config_dict['agents']:
                    if not isinstance(agent_id, str):
                        raise InvalidConfigError(
                            f"Agent must be a string (agent ID), got {type(agent_id)}")

                    if agent_id not in valid_agent_ids:
                        raise InvalidConfigError(
                            f"Unknown agent ID: {agent_id}. Available agents: {', '.join(valid_agent_ids)}"
                        )

        return config_dict

    except yaml.YAMLError as e:
        raise InvalidConfigError(f"Invalid YAML format: {str(e)}")


# Use the default config from schemas module
DEFAULT_CONFIG = get_default_benchmark_yaml()


@bp.route('/')
@handle_errors
def index():
    """Benchmark configuration page"""
    # Get saved agents
    agents = get_available_agents()

    # Create default agents if none exist
    if not agents:
        agent_manager = AgentManager()
        agent_manager.create_default_agents()
        agents = get_available_agents()

    # Add agent IDs to the default YAML config to show in the example
    agent_ids = [agent['id'] for agent in agents[:2]] if agents else []

    # Modify the config to include agent_id examples
    config = DEFAULT_CONFIG
    if agent_ids:
        # Add comment about using saved agents
        config_lines = config.split('\n')
        for i, line in enumerate(config_lines):
            if line.strip().startswith('# Agent configurations'):
                config_lines.insert(i + 1, '#')
                config_lines.insert(i + 2, '# You can use saved agents by agent_id:')
                config_lines.insert(i + 3, f'# - agent_id: {agent_ids[0]}')
                if len(agent_ids) > 1:
                    config_lines.insert(i + 4, f'# - agent_id: {agent_ids[1]}')
                break
        config = '\n'.join(config_lines)

    return render_template('benchmark/index.html', default_config=config, saved_agents=agents)


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
        # Validate the config
        config_dict = validate_benchmark_config(data['config'])

        # Get the current Flask app
        flask_app = current_app._get_current_object()

        # Start benchmark using our utility function
        benchmark_id = start_benchmark(config_dict, flask_app)

        return jsonify({
            'success': True,
            'message': 'Benchmark started successfully',
            'benchmark_id': benchmark_id
        })

    except Exception as e:
        logger.error(f"Failed to run benchmark: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/status/<benchmark_id>')
@handle_errors
def status(benchmark_id):
    """Get benchmark status"""
    # First check active benchmarks from our utility
    benchmark_status = get_benchmark_status(benchmark_id)
    if benchmark_status:
        return jsonify({
            'success': True,
            'benchmark_id': benchmark_id,
            'status': benchmark_status.status,
            'progress': benchmark_status.progress,
            'current_task': benchmark_status.current_task
        })

    # If not active, check database for completed benchmark
    benchmark_run = BenchmarkRun.query.filter_by(benchmark_id=benchmark_id).first()
    if benchmark_run:
        return jsonify({
            'success':
                True,
            'benchmark_id':
                benchmark_id,
            'status':
                benchmark_run.status,
            'progress':
                100 if benchmark_run.status == 'complete' else 0,
            'current_task':
                'Complete'
                if benchmark_run.status == 'complete' else benchmark_run.error or 'Unknown'
        })

    return jsonify({'success': False, 'error': f'Benchmark {benchmark_id} not found'}), 404


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

    # Add active benchmarks from our utility
    active_benchmarks_dict = list_active_benchmarks()
    for benchmark_id, status in active_benchmarks_dict.items():
        if status['status'] != 'complete' and not any(r['benchmark_id'] == benchmark_id
                                                      for r in results):
            # Create a result entry for active benchmarks
            results.append({
                'id': None,
                'benchmark_id': benchmark_id,
                'name': 'Running Benchmark',
                'status': status['status'],
                'timestamp': status['start_time'],
                'end_time': None
            })

    return jsonify({'success': True, 'results': results})
