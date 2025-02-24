"""Quest runner and monitor blueprint"""
from flask import Blueprint, render_template, request, jsonify
from pathlib import Path
import glob
import json
from datetime import datetime
import logging
import os

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
from llm_quest_benchmark.core.runner import run_quest_with_timeout
from llm_quest_benchmark.agents.agent_factory import create_agent
from llm_quest_benchmark.environments.state import QuestOutcome
from ..models.database import db, Run, Step
from ..utils.errors import handle_errors, validate_quest_file, validate_model

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

@bp.route('/')
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
    """Run a quest with specified configuration"""
    logger.debug("Received quest run request")
    if not request.is_json:
        logger.error("Request is not JSON")
        return jsonify({'success': False, 'error': 'Request must be JSON'}), 400

    data = request.get_json()
    logger.debug(f"Request data: {data}")

    try:
        # Extract and validate quest configuration
        quest_name = data.get('quest')
        quest_path = Path("quests") / quest_name
        logger.debug(f"Quest path: {quest_path}")
        validate_quest_file(str(quest_path))

        # Extract and validate agent configuration
        model = data.get('model', DEFAULT_MODEL)
        validate_model(model)
        temperature = float(data.get('temperature', DEFAULT_TEMPERATURE))
        template = data.get('template', DEFAULT_TEMPLATE)
        logger.debug(f"Agent config - model: {model}, temperature: {temperature}, template: {template}")

        # Create agent with CLI-compatible configuration
        logger.info(f"Starting quest '{quest_name}' with {model} agent using {template} template")
        agent = create_agent(
            model=model,
            temperature=temperature,
            system_template=SYSTEM_ROLE_TEMPLATE,
            action_template=f"{template}.jinja",
            skip_single=True,
            debug=True
        )
        logger.debug(f"Agent created: {agent}")

        try:
            # Create run record
            logger.debug("Creating run record")
            run = Run(
                quest_name=quest_name,
                agent_id=model,
                agent_config=json.dumps({
                    'model': model,
                    'temperature': temperature,
                    'template': template,
                    'skip_single': True,
                    'debug': True
                })
            )
            db.session.add(run)
            db.session.commit()
            logger.debug(f"Run record created with ID: {run.id}")

            def store_step(event: str, step_data=None):
                """Store step in database"""
                logger.debug(f"Received event: {event}")
                if event != "game_state" or not step_data:
                    logger.debug(f"Skipping event {event} - no step data or not game_state")
                    return

                try:
                    logger.debug(f"Storing step data: {step_data}")
                    step = Step(
                        run_id=run.id,
                        step=step_data.step,
                        location_id=step_data.location_id,
                        observation=step_data.observation,
                        choices=json.dumps([c.dict() for c in step_data.choices]) if step_data.choices else None,
                        action=step_data.action,
                        llm_response=json.dumps(step_data.llm_response.dict()) if step_data.llm_response else None
                    )
                    db.session.add(step)
                    db.session.commit()
                    logger.debug(f"Step stored successfully: {step.id}")
                except Exception as e:
                    logger.error(f"Failed to store step: {e}", exc_info=True)

            # Run quest using the CLI's run_quest_with_timeout
            logger.info(f"Starting quest run: {quest_path}")
            try:
                outcome = run_quest_with_timeout(
                    quest_path=str(quest_path),
                    agent=agent,
                    timeout=DEFAULT_QUEST_TIMEOUT,
                    callbacks=[store_step],
                    debug=True
                )
                logger.info(f"Quest run completed with outcome: {outcome}")
            except RuntimeError as e:
                if "No initial state received from TypeScript bridge" in str(e):
                    logger.error("Failed to initialize TypeScript bridge")
                    raise RuntimeError("Failed to initialize quest. Please try again.")
                raise

            # Update run with outcome
            run.end_time = datetime.utcnow()
            run.outcome = outcome.name if isinstance(outcome, QuestOutcome) else str(outcome)
            db.session.commit()
            logger.debug(f"Run record updated with outcome: {run.outcome}")

            return jsonify({
                'success': True,
                'run_id': run.id,
                'outcome': run.outcome
            })

        except Exception as e:
            # Rollback on error
            db.session.rollback()
            logger.error(f"Error running quest: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    except Exception as e:
        logger.error(f"Error in run_quest: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

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