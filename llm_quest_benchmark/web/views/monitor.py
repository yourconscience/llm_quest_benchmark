"""Quest runner and monitor blueprint"""
from flask import Blueprint, render_template, request, jsonify
from pathlib import Path
import glob
import json
import logging
import os
from typing import Any, Dict, List, Optional
import traceback

logger = logging.getLogger(__name__)

from llm_quest_benchmark.constants import (
    MODEL_CHOICES,
    DEFAULT_MODEL,
    DEFAULT_TEMPLATE,
    DEFAULT_TEMPERATURE,
    DEFAULT_QUEST_TIMEOUT,
    SYSTEM_ROLE_TEMPLATE,
    PROMPT_TEMPLATES_DIR,
)

from llm_quest_benchmark.agents.agent_factory import create_agent
from ..models.database import db, Run, Step
from ..utils.errors import handle_errors, validate_quest_file, validate_model, validate_choice
from ..utils.web_runner import run_quest_with_db_logging, take_manual_step
from llm_quest_benchmark.dataclasses.config import AgentConfig

# Initialize TypeScript bridge
os.environ['NODE_OPTIONS'] = '--openssl-legacy-provider'

bp = Blueprint('monitor', __name__, url_prefix='/monitor')

def get_available_quests():
    """Get list of available quests recursively"""
    quest_files = []
    for root, _, files in os.walk("quests"):
        for file in files:
            if file.endswith(".qm"):
                rel_path = os.path.relpath(os.path.join(root, file), "quests")
                quest_files.append(rel_path)
    logger.debug(f"Found quest files: {quest_files}")
    return sorted(quest_files)

def get_available_templates():
    """Get list of available templates"""
    template_files = glob.glob(str(PROMPT_TEMPLATES_DIR / "*.jinja"))
    logger.debug(f"Found template files: {template_files}")
    # Return template names without .jinja extension for display
    templates = [Path(f).stem for f in template_files]
    logger.debug(f"Available templates: {templates}")
    return sorted(templates)  # Sort for consistent display

@bp.route('')
@handle_errors
def index():
    """Quest runner and monitor page"""
    logger.debug("Loading quest runner page")
    quests = get_available_quests()
    templates = get_available_templates()
    logger.debug(f"Available quests: {quests}")
    logger.debug(f"Available templates: {templates}")
    return render_template('monitor/index.html',
                         quests=quests,
                         templates=templates,
                         models=MODEL_CHOICES,
                         default_model=DEFAULT_MODEL,
                         default_template=DEFAULT_TEMPLATE.replace('.jinja', ''),
                         default_temperature=DEFAULT_TEMPERATURE)

@bp.route('/run', methods=['POST'])
@handle_errors
def run_quest():
    """Create and start a new quest run"""
    logger.debug("Received quest run request")
    if not request.is_json:
        logger.error("Request is not JSON")
        return jsonify({'success': False, 'error': 'Request must be JSON'}), 400

    data = request.get_json()
    logger.debug(f"Request data: {data}")

    # Extract quest configuration
    quest_name = data.get('quest')
    quest_path = f"quests/{quest_name}"
    model = data.get('model', DEFAULT_MODEL)
    timeout = int(data.get('timeout', DEFAULT_QUEST_TIMEOUT))
    template = data.get('template', DEFAULT_TEMPLATE)
    temperature = float(data.get('temperature', DEFAULT_TEMPERATURE))

    # Validate inputs
    validate_quest_file(quest_path)
    validate_model(model)

    logger.debug(f"Quest path: {quest_path}")

    # Create agent config
    agent_config = AgentConfig(
        model=model,
        system_template=SYSTEM_ROLE_TEMPLATE,
        action_template=template + '.jinja',
        temperature=temperature,
        skip_single=True,
        debug=True
    )

    # Get agent_id from agent_config
    agent_id = agent_config.agent_id

    # Create run record with agent_config
    run = Run(
        quest_file=quest_path,
        quest_name=Path(quest_name).stem,
        agent_id=agent_id,
        agent_config=agent_config.__dict__
    )
    db.session.add(run)
    db.session.commit()
    logger.debug(f"Run record created with ID: {run.id}")

    # Create agent
    agent = create_agent(
        model=model,
        system_template=SYSTEM_ROLE_TEMPLATE,
        action_template=template + '.jinja',
        temperature=temperature,
        skip_single=True,
        debug=True
    )

    # Run quest and log to database
    result = run_quest_with_db_logging(
        quest_path=quest_path,
        agent=agent,
        run_record=run,
        timeout=timeout,
        debug=True,
        request=request
    )

    return jsonify(result)

@bp.route('/init', methods=['POST'])
@handle_errors
def init_quest_route():
    """Create and start a new quest run (initialization only)"""
    logger.debug("Received quest initialization request")
    if not request.is_json:
        logger.error("Request is not JSON")
        return jsonify({'success': False, 'error': 'Request must be JSON'}), 400

    data = request.get_json()
    logger.debug(f"Request data: {data}")

    try:
        # Extract quest configuration
        quest_name = data.get('quest')
        quest_path = f"quests/{quest_name}"
        model = data.get('model', DEFAULT_MODEL)
        timeout = int(data.get('timeout', DEFAULT_QUEST_TIMEOUT))
        template = data.get('template', DEFAULT_TEMPLATE)
        temperature = float(data.get('temperature', DEFAULT_TEMPERATURE))

        # Validate inputs
        validate_quest_file(quest_path)
        validate_model(model)

        logger.debug(f"Quest path: {quest_path}")

        # Create agent config
        agent_config = AgentConfig(
            model=model,
            system_template=SYSTEM_ROLE_TEMPLATE,
            action_template=template + '.jinja',
            temperature=temperature,
            skip_single=True,
            debug=True
        )

        # Get agent_id from agent_config
        agent_id = agent_config.agent_id

        # Create run record with agent_config
        run = Run(
            quest_file=quest_path,
            quest_name=Path(quest_name).stem,
            agent_id=agent_id,
            agent_config=agent_config.__dict__
        )
        db.session.add(run)
        db.session.commit()
        logger.debug(f"Run record created with ID: {run.id}")

        # Create agent
        agent = create_agent(
            model=model,
            system_template=SYSTEM_ROLE_TEMPLATE,
            action_template=template + '.jinja',
            temperature=temperature,
            skip_single=True,
            debug=True
        )

        # Run quest and log to database
        result = run_quest_with_db_logging(
            quest_path=quest_path,
            agent=agent,
            run_record=run,
            timeout=timeout,
            debug=True,
            request=request
        )

        # Explicitly ensure end_time is None for initialization
        run.end_time = None
        db.session.commit()

        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in init_quest_route: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/step/<int:run_id>', methods=['POST'])
@handle_errors
def take_step_route(run_id):
    """Take a step in an existing quest run"""
    logger.debug(f"Received step request for run {run_id}")
    if not request.is_json:
        logger.error("Request is not JSON")
        return jsonify({'success': False, 'error': 'Request must be JSON'}), 400

    data = request.get_json()
    choice_num = data.get('choice')
    if choice_num is None:
        return jsonify({'success': False, 'error': 'No choice provided'}), 400

    # Use the utility function to take a step
    result = take_manual_step(run_id, choice_num, debug=True)

    # Return result as JSON
    if result['success']:
        return jsonify(result)
    else:
        return jsonify(result), 400

@bp.route('/runs')
@handle_errors
def list_runs():
    """List all quest runs"""
    logger.debug("Fetching all runs")
    runs = Run.query.order_by(Run.start_time.desc()).all()
    logger.debug(f"Found {len(runs)} runs")
    return jsonify({
        'success': True,
        'runs': [run.to_dict() for run in runs]
    })

@bp.route('/runs/<int:run_id>')
@handle_errors
def get_run(run_id):
    """Get details of a specific run"""
    logger.debug(f"Fetching run details for ID: {run_id}")
    run = Run.query.get_or_404(run_id)
    steps = Step.query.filter_by(run_id=run_id).order_by(Step.step).all()
    logger.debug(f"Found run with {len(steps)} steps")

    # Convert steps to dictionary form
    step_dicts = [step.to_dict() for step in steps]

    return jsonify({
        'success': True,
        'run': run.to_dict(),
        'steps': step_dicts
    })

@bp.route('/template/<template_name>')
@handle_errors
def get_template_content(template_name):
    """Get content of a template file"""
    template_path = PROMPT_TEMPLATES_DIR / f"{template_name}.jinja"
    if not template_path.exists():
        return jsonify({'success': False, 'error': 'Template not found'}), 404

    with open(template_path, 'r') as f:
        content = f.read()

    return jsonify({
        'success': True,
        'content': content
    })