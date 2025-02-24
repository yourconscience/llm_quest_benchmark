"""Quest runner and monitor blueprint"""
from flask import Blueprint, render_template, request, jsonify
from pathlib import Path
import glob
import json
from datetime import datetime
import logging
import os
import random
from typing import Any

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
from llm_quest_benchmark.environments.qm import QMPlayerEnv as QuestEnvironment
from llm_quest_benchmark.agents.agent_factory import create_agent
from llm_quest_benchmark.core.runner import run_quest_with_timeout
from llm_quest_benchmark.environments.state import QuestOutcome
from ..models.database import db, Run, Step
from ..utils.errors import handle_errors

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

    try:
        # Extract quest configuration
        quest_name = data.get('quest')
        quest_path = f"quests/{quest_name}"
        model = data.get('model', DEFAULT_MODEL)
        timeout = int(data.get('timeout', DEFAULT_QUEST_TIMEOUT))
        template = data.get('template', DEFAULT_TEMPLATE)
        temperature = float(data.get('temperature', DEFAULT_TEMPERATURE))
        logger.debug(f"Quest path: {quest_path}")

        # Create run record
        run = Run(
            quest_name=quest_name,
            agent_id=model,
            agent_config=json.dumps({
                'model': model,
                'template': template,
                'temperature': temperature,
                'debug': True
            })
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

        # Run quest using the runner
        steps = []
        def step_callback(event: str, data: Any) -> None:
            if event == "game_state":
                step_data = {
                    'step': data.step,
                    'location_id': data.location_id,
                    'observation': data.observation,
                    'choices': data.choices,
                    'action': data.action,
                    'llm_response': data.llm_response
                }
                steps.append(step_data)

                # Store in database
                step = Step(
                    run_id=run.id,
                    step=data.step,
                    location_id=data.location_id,
                    observation=data.observation,
                    choices=json.dumps(data.choices),
                    action=data.action
                )
                db.session.add(step)
                db.session.commit()

        # Run quest
        outcome = run_quest_with_timeout(
            quest_path=quest_path,
            agent=agent,
            timeout=timeout,
            debug=True,
            callbacks=[step_callback]
        )

        if outcome is None:
            run.outcome = 'TIMEOUT'
        else:
            run.outcome = 'SUCCESS' if outcome == QuestOutcome.SUCCESS else 'FAILURE'

        run.end_time = datetime.utcnow()
        db.session.commit()

        return jsonify({
            'success': True,
            'run_id': run.id,
            'steps': steps,
            'outcome': run.outcome
        })

    except Exception as e:
        logger.error(f"Error in run_quest: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@bp.route('/step/<int:run_id>', methods=['POST'])
@handle_errors
def take_step(run_id):
    """Take a step in an existing quest run"""
    logger.debug(f"Received step request for run {run_id}")
    if not request.is_json:
        logger.error("Request is not JSON")
        return jsonify({'success': False, 'error': 'Request must be JSON'}), 400

    data = request.get_json()
    choice_num = data.get('choice')
    if choice_num is None:
        return jsonify({'success': False, 'error': 'No choice provided'}), 400

    try:
        # Get run and verify it exists
        run = Run.query.get_or_404(run_id)
        if run.end_time:
            return jsonify({'success': False, 'error': 'Quest run already completed'}), 400

        # Get last step
        last_step = Step.query.filter_by(run_id=run_id).order_by(Step.step.desc()).first()
        if not last_step:
            return jsonify({'success': False, 'error': 'No steps found for run'}), 400

        # Initialize environment
        quest_path = f"quests/{run.quest_name}"
        env = QuestEnvironment(quest_path, debug=True)

        try:
            # Start game and replay steps to current state
            env.reset()
            for step in Step.query.filter_by(run_id=run_id).order_by(Step.step).all():
                if step.action:
                    env.step(int(step.action))

            # Take new step
            new_state = env.step(int(choice_num))

            # Store step
            step = Step(
                run_id=run_id,
                step=last_step.step + 1,
                location_id=new_state['location_id'],
                observation=new_state['text'],
                choices=json.dumps(new_state['choices']),
                action=str(choice_num)
            )
            db.session.add(step)

            # Update run if game ended
            if new_state['game_ended']:
                run.end_time = datetime.utcnow()
                run.outcome = 'SUCCESS'

            db.session.commit()

            return jsonify({
                'success': True,
                'state': {
                    'step': step.step,
                    'location_id': new_state['location_id'],
                    'observation': new_state['text'],
                    'choices': new_state['choices'],
                    'game_ended': new_state['game_ended']
                }
            })

        finally:
            env.close()

    except Exception as e:
        logger.error(f"Error in take_step: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

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
    return jsonify({
        'success': True,
        'run': run.to_dict(),
        'steps': [step.to_dict() for step in steps]
    })

@bp.route('/template/<template_name>')
@handle_errors
def get_template_content(template_name):
    """Get content of a template file"""
    try:
        template_path = PROMPT_TEMPLATES_DIR / f"{template_name}.jinja"
        if not template_path.exists():
            return jsonify({'success': False, 'error': 'Template not found'}), 404

        with open(template_path, 'r') as f:
            content = f.read()

        return jsonify({
            'success': True,
            'content': content
        })
    except Exception as e:
        logger.error(f"Error reading template: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400