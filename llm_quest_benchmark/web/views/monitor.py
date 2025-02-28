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
from llm_quest_benchmark.utils.text_processor import clean_qm_text
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

    # Get run as dictionary and ensure it has quest_name derived from quest_file
    run_dict = run.to_dict()
    if 'quest_file' in run_dict and run_dict['quest_file']:
        run_dict['quest_name'] = Path(run_dict['quest_file']).stem
    elif 'quest_name' not in run_dict or not run_dict['quest_name']:
        run_dict['quest_name'] = "Unknown"

    return jsonify({
        'success': True,
        'run': run_dict,
        'steps': step_dicts,
        'outcome': run.outcome
    })

@bp.route('/runs/<int:run_id>/readable')
@handle_errors
def get_run_readable(run_id):
    """Get human-readable details of a specific run"""
    logger.debug(f"Fetching human-readable run details for ID: {run_id}")
    run = Run.query.get_or_404(run_id)
    steps = Step.query.filter_by(run_id=run_id).order_by(Step.step).all()
    logger.debug(f"Found run with {len(steps)} steps")

    # Format the run details in a human-readable way
    readable_output = []

    # Extract quest name from quest_file if available, otherwise use quest_name
    quest_name = Path(run.quest_file).stem if run.quest_file else run.quest_name or "Unknown"

    # Run header
    readable_output.append(f"QUEST: {quest_name}")

    # Get agent name from agent_config if available
    agent_name = "Unknown"
    if run.agent_config and isinstance(run.agent_config, dict) and 'model' in run.agent_config:
        agent_name = run.agent_config['model']
    elif run.agent_id:
        agent_name = run.agent_id

    readable_output.append(f"AGENT: {agent_name}")

    # Show total steps instead of start time
    readable_output.append(f"TOTAL STEPS: {len(steps)}")

    if run.end_time:
        readable_output.append(f"END TIME: {run.end_time}")
    if run.outcome:
        readable_output.append(f"OUTCOME: {run.outcome}")
    readable_output.append("")
    readable_output.append("========== QUEST PLAYTHROUGH ==========")

    # Format each step
    for i, step in enumerate(steps):
        # Step header
        readable_output.append("")
        readable_output.append(f"----- STEP {step.step} -----")
        readable_output.append("")

        # Observation - text is already cleaned at the source
        readable_output.append(f"{step.observation}")
        readable_output.append("")

        # Choices - text is already cleaned at the source
        if step.choices and len(step.choices) > 0:
            readable_output.append("Available choices:")
            for i, choice in enumerate(step.choices):
                readable_output.append(f"{i+1}. {choice['text']}")
            readable_output.append("")

        # Action taken and LLM response from the NEXT step (if available)
        # This fixes the issue where LLM response for step N is actually for choices from step N-1
        if step.action:
            # Find the chosen option text
            choice_text = "Unknown choice"
            if step.choices and len(step.choices) > 0:
                choice_index = int(step.action) - 1
                if 0 <= choice_index < len(step.choices):
                    choice_text = step.choices[choice_index]['text']

            readable_output.append(f"Selected option {step.action}: {choice_text}")
            readable_output.append("")

        # Get the NEXT step's LLM response (if available) which corresponds to THIS step's choices
        next_step_index = i + 1
        if next_step_index < len(steps) and steps[next_step_index].llm_response:
            next_step = steps[next_step_index]
            llm_response = next_step.llm_response

            # Process the LLM response to extract reasoning and analysis
            try:
                # If llm_response is a string, try to parse it as JSON
                if isinstance(llm_response, str):
                    try:
                        llm_response = json.loads(llm_response)
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse LLM response as JSON: {llm_response}")
                        llm_response = {}

                # Handle both dictionary and object-like structures
                if llm_response:
                    # Try to get reasoning - handle both attribute and dictionary access
                    reasoning = None
                    if isinstance(llm_response, dict) and 'reasoning' in llm_response:
                        reasoning = llm_response['reasoning']
                    elif hasattr(llm_response, 'reasoning'):
                        reasoning = llm_response.reasoning

                    if reasoning:
                        readable_output.append(f"Reasoning: {reasoning}")
                        readable_output.append("")

                    # Try to get analysis - handle both attribute and dictionary access
                    analysis = None
                    if isinstance(llm_response, dict) and 'analysis' in llm_response:
                        analysis = llm_response['analysis']
                    elif hasattr(llm_response, 'analysis'):
                        analysis = llm_response.analysis

                    if analysis:
                        readable_output.append(f"Analysis: {analysis}")
                        readable_output.append("")
            except Exception as e:
                logger.error(f"Error processing LLM response: {e}")
                logger.error(f"LLM response type: {type(llm_response)}")
                logger.error(f"LLM response: {llm_response}")

    # Final outcome
    if run.outcome:
        readable_output.append("")
        readable_output.append(f"========== QUEST OUTCOME: {run.outcome} ==========")

    return jsonify({
        'success': True,
        'readable_output': '\n'.join(readable_output)
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