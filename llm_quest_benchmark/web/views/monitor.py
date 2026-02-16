"""Quest runner and monitor blueprint"""
from flask import Blueprint, render_template, request, jsonify, current_app
from pathlib import Path
from datetime import datetime
import glob
import json
import logging
import os
import threading
from typing import Any, Dict, List, Optional

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
from llm_quest_benchmark.utils.text_processor import clean_qm_text, wrap_text
from ..models.database import db, Run, Step, RunEvent
from ..utils.errors import (
    handle_errors,
    validate_quest_file,
    validate_model,
    validate_choice,
    QuestNotFoundError,
)
from ..utils.web_runner import run_quest_with_db_logging, take_manual_step
from llm_quest_benchmark.schemas.config import AgentConfig

# Initialize TypeScript bridge
os.environ['NODE_OPTIONS'] = '--openssl-legacy-provider'

bp = Blueprint('monitor', __name__, url_prefix='/monitor')
active_run_jobs: Dict[int, Dict[str, Any]] = {}
active_run_lock = threading.Lock()

def get_available_quests():
    """Get list of available quests using the registry"""
    from llm_quest_benchmark.core.quest_registry import get_registry
    from llm_quest_benchmark.constants import QUEST_ROOT_DIRECTORY
    
    registry = get_registry()
    
    # Get unique quests only (filter out duplicates)
    quest_infos = registry.get_unique_quests()
    
    # Return paths relative to QUEST_ROOT_DIRECTORY
    quest_files = [info.relative_path for info in quest_infos]
    
    logger.debug(f"Found {len(quest_files)} unique quest files")
    return sorted(quest_files)

def get_available_templates():
    """Get list of available templates"""
    template_files = glob.glob(str(PROMPT_TEMPLATES_DIR / "*.jinja"))
    logger.debug(f"Found template files: {template_files}")
    # Return template names without .jinja extension for display
    templates = [Path(f).stem for f in template_files]
    logger.debug(f"Available templates: {templates}")
    return sorted(templates)  # Sort for consistent display


def _resolve_quest_path(quest_value: str) -> str:
    """Resolve incoming quest value via registry without hardcoded path prefixes."""
    from llm_quest_benchmark.core.quest_registry import get_registry

    if not quest_value:
        raise QuestNotFoundError("Quest path not found: empty value", status_code=404)

    validate_quest_file(quest_value)
    registry = get_registry()
    resolved = registry.resolve_quest_path(quest_value)
    if not resolved:
        raise QuestNotFoundError(f"Quest path not found: {quest_value}", status_code=404)
    return str(resolved[0])


def _parse_run_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse and validate run payload from request body."""
    quest_name = data.get('quest')
    quest_path = _resolve_quest_path(quest_name)
    model = data.get('model', DEFAULT_MODEL)
    timeout = int(data.get('timeout', DEFAULT_QUEST_TIMEOUT))
    template = data.get('template', DEFAULT_TEMPLATE)
    temperature = float(data.get('temperature', DEFAULT_TEMPERATURE))
    validate_model(model)
    return {
        "quest_name": quest_name,
        "quest_path": quest_path,
        "model": model,
        "timeout": timeout,
        "template": template,
        "temperature": temperature,
    }


def _build_agent_and_run(payload: Dict[str, Any], create_agent_instance: bool = True) -> Dict[str, Any]:
    """Create AgentConfig/Run and optionally instantiate an agent."""
    agent_config = AgentConfig(
        model=payload["model"],
        system_template=SYSTEM_ROLE_TEMPLATE,
        action_template=payload["template"] + '.jinja',
        temperature=payload["temperature"],
        skip_single=True,
        debug=True
    )

    run = Run(
        quest_file=payload["quest_path"],
        quest_name=Path(payload["quest_path"]).stem,
        agent_id=agent_config.agent_id,
        agent_config=agent_config.__dict__,
    )
    db.session.add(run)
    db.session.commit()

    result: Dict[str, Any] = {"agent_config": agent_config, "run": run}
    if create_agent_instance:
        agent = create_agent(
            model=payload["model"],
            system_template=SYSTEM_ROLE_TEMPLATE,
            action_template=payload["template"] + '.jinja',
            temperature=payload["temperature"],
            skip_single=True,
            debug=True
        )
        result["agent"] = agent
    return result


def _update_active_run(run_id: int, **kwargs: Any) -> None:
    with active_run_lock:
        state = active_run_jobs.setdefault(run_id, {})
        state.update(kwargs)
        state["updated_at"] = datetime.utcnow().isoformat()


def _get_active_run(run_id: int) -> Dict[str, Any]:
    with active_run_lock:
        return dict(active_run_jobs.get(run_id, {}))


def _run_quest_background(
    app,
    run_id: int,
    quest_path: str,
    model: str,
    template: str,
    temperature: float,
    timeout: int,
) -> None:
    """Background worker that executes quest run and updates job state."""
    with app.app_context():
        run = Run.query.get(run_id)
        if not run:
            _update_active_run(run_id, status="error", error="Run not found")
            return

        _update_active_run(
            run_id,
            status="running",
            current_task=f"Running {Path(quest_path).name} with {model}",
            step_count=0,
            event_count=0,
        )

        def event_sink(event_name: str, payload: Dict[str, Any]) -> None:
            if event_name == "step":
                _update_active_run(
                    run_id,
                    step_count=int(payload.get("step") or 0),
                    event_count=int(payload.get("event_id") or 0),
                    current_task=f"Step {payload.get('step')} at location {payload.get('location_id')}",
                )
            elif event_name == "timeout":
                _update_active_run(run_id, current_task="Timed out")
            elif event_name == "outcome":
                _update_active_run(
                    run_id,
                    current_task=f"Finished with {payload.get('outcome')}",
                    outcome=payload.get("outcome"),
                    event_count=int(payload.get("event_id") or 0),
                )

        try:
            agent = create_agent(
                model=model,
                system_template=SYSTEM_ROLE_TEMPLATE,
                action_template=template + '.jinja',
                temperature=temperature,
                skip_single=True,
                debug=True
            )
            run_quest_with_db_logging(
                quest_path=quest_path,
                agent=agent,
                run_record=run,
                timeout=timeout,
                debug=True,
                request=None,
                event_sink=event_sink,
            )
            db.session.refresh(run)
            _update_active_run(
                run_id,
                status="complete",
                outcome=run.outcome,
                current_task="Completed",
            )
        except Exception as e:
            logger.error("Background run failed for %s: %s", run_id, e, exc_info=True)
            run.end_time = datetime.utcnow()
            run.outcome = "ERROR"
            db.session.add(
                RunEvent(
                    run_id=run_id,
                    event_type="error",
                    payload={"message": str(e)},
                )
            )
            db.session.commit()
            _update_active_run(
                run_id,
                status="error",
                error=str(e),
                current_task="Error",
            )

@bp.route('')
@handle_errors
def index():
    """Quest runner and monitor page"""
    logger.debug("Loading quest runner page")
    quests = get_available_quests()
    templates = get_available_templates()
    logger.debug(f"Available quests: {quests}")
    logger.debug(f"Available templates: {templates}")
    # Find the Diehard.qm quest in the list of quests (default to first in the list if not found)
    default_quest = next((q for q in quests if "Diehard.qm" in q), quests[0] if quests else "")
    
    return render_template('monitor/index.html',
                         quests=quests,
                         templates=templates,
                         models=MODEL_CHOICES,
                         default_model=DEFAULT_MODEL,
                         default_template=DEFAULT_TEMPLATE.replace('.jinja', ''),
                         default_quest=default_quest,
                         default_temperature=DEFAULT_TEMPERATURE)

@bp.route('/run', methods=['POST'])
@handle_errors
def run_quest():
    """Create and run a quest synchronously (legacy mode)."""
    logger.debug("Received quest run request")
    if not request.is_json:
        logger.error("Request is not JSON")
        return jsonify({'success': False, 'error': 'Request must be JSON'}), 400

    data = request.get_json()
    payload = _parse_run_payload(data)
    created = _build_agent_and_run(payload)
    run = created["run"]
    agent = created["agent"]
    logger.debug(f"Run record created with ID: {run.id}")

    # Run quest and log to database
    result = run_quest_with_db_logging(
        quest_path=payload["quest_path"],
        agent=agent,
        run_record=run,
        timeout=payload["timeout"],
        debug=True,
        request=request
    )

    return jsonify(result)


@bp.route('/run_async', methods=['POST'])
@handle_errors
def run_quest_async():
    """Create a run and execute it in a background thread for live polling."""
    logger.debug("Received async quest run request")
    if not request.is_json:
        return jsonify({'success': False, 'error': 'Request must be JSON'}), 400

    payload = _parse_run_payload(request.get_json())
    created = _build_agent_and_run(payload, create_agent_instance=False)
    run = created["run"]

    _update_active_run(
        run.id,
        status="queued",
        current_task="Queued",
        step_count=0,
        event_count=0,
    )

    app = current_app._get_current_object()
    thread = threading.Thread(
        target=_run_quest_background,
        kwargs={
            "app": app,
            "run_id": run.id,
            "quest_path": payload["quest_path"],
            "model": payload["model"],
            "template": payload["template"],
            "temperature": payload["temperature"],
            "timeout": payload["timeout"],
        },
        daemon=True,
    )
    thread.start()

    return jsonify({
        "success": True,
        "run_id": run.id,
        "status": "queued",
        "status_url": f"/monitor/run_status/{run.id}",
        "events_url": f"/monitor/runs/{run.id}/events",
    })


@bp.route('/run_status/<int:run_id>')
@handle_errors
def run_status(run_id: int):
    """Get async run status and current counters."""
    run = Run.query.get_or_404(run_id)
    active = _get_active_run(run_id)
    latest_event = db.session.query(db.func.max(RunEvent.id)).filter_by(run_id=run_id).scalar() or 0
    step_count = Step.query.filter_by(run_id=run_id).count()

    status = active.get("status")
    if not status:
        if run.end_time:
            status = "complete" if run.outcome != "ERROR" else "error"
        else:
            status = "running"
    progress = 100 if status in {"complete", "error"} else 5

    return jsonify({
        "success": True,
        "run_id": run_id,
        "status": status,
        "progress": progress,
        "outcome": run.outcome,
        "step_count": step_count,
        "event_count": latest_event,
        "current_task": active.get("current_task", "Running"),
        "error": active.get("error"),
        "updated_at": active.get("updated_at"),
    })

@bp.route('/init', methods=['POST'])
@handle_errors
def init_quest_route():
    """Create and start a new quest run (initialization only)"""
    logger.debug("Received quest initialization request")
    if not request.is_json:
        logger.error("Request is not JSON")
        return jsonify({'success': False, 'error': 'Request must be JSON'}), 400

    payload = _parse_run_payload(request.get_json())
    created = _build_agent_and_run(payload)
    run = created["run"]
    agent = created["agent"]
    logger.debug(f"Run record created with ID: {run.id}")

    # Run quest and log to database
    result = run_quest_with_db_logging(
        quest_path=payload["quest_path"],
        agent=agent,
        run_record=run,
        timeout=payload["timeout"],
        debug=True,
        request=request
    )

    # Explicitly ensure end_time is None for initialization
    run.end_time = None
    db.session.commit()

    return jsonify(result)

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

    # Process steps to add wrapped text for better display
    for step in step_dicts:
        if 'observation' in step and step['observation']:
            step['wrapped_observation'] = wrap_text(step['observation'], width=150)
        
        if 'choices' in step and step['choices']:
            for choice in step['choices']:
                if 'text' in choice and choice['text']:
                    choice['wrapped_text'] = wrap_text(choice['text'], width=120)

    return jsonify({
        'success': True,
        'run': run_dict,
        'steps': step_dicts,
        'outcome': run.outcome
    })


@bp.route('/runs/<int:run_id>/events')
@handle_errors
def get_run_events(run_id: int):
    """Return structured run events for live monitor polling."""
    Run.query.get_or_404(run_id)
    after_id = int(request.args.get("after_id", 0))
    limit = min(int(request.args.get("limit", 200)), 1000)
    compact = str(request.args.get("compact", "0")).lower() in {"1", "true", "yes"}

    events = (
        RunEvent.query
        .filter(RunEvent.run_id == run_id, RunEvent.id > after_id)
        .order_by(RunEvent.id.asc())
        .limit(limit)
        .all()
    )
    event_rows = [e.to_dict() for e in events]
    if compact:
        for row in event_rows:
            payload = row.get("payload") or {}
            if isinstance(payload, dict):
                obs = payload.get("observation")
                if isinstance(obs, str) and len(obs) > 320:
                    payload["observation"] = obs[:320] + "..."
                llm_decision = payload.get("llm_decision")
                if isinstance(llm_decision, dict):
                    for k in ("reasoning", "analysis"):
                        val = llm_decision.get(k)
                        if isinstance(val, str) and len(val) > 200:
                            llm_decision[k] = val[:200] + "..."

    return jsonify({
        "success": True,
        "run_id": run_id,
        "events": event_rows,
        "last_event_id": events[-1].id if events else after_id,
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
    agent_name = run.agent_id if run.agent_id else "Unknown"
    if run.agent_config and isinstance(run.agent_config, dict) and 'model' in run.agent_config:
        agent_name = f"{agent_name} ({run.agent_config['model']})"
    
    readable_output.append(f"AGENT: {agent_name}")

    # Show number of steps instead of start time
    readable_output.append(f"STEPS: {len(steps)}")

    if run.end_time:
        readable_output.append(f"END TIME: {run.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
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

        # Observation - wrap the text for better readability
        wrapped_observation = wrap_text(step.observation, width=150)
        readable_output.append(f"{wrapped_observation}")
        readable_output.append("")

        # Choices - text is already cleaned at the source
        if step.choices and len(step.choices) > 0:
            readable_output.append("Available choices:")
            for i, choice in enumerate(step.choices):
                wrapped_choice = wrap_text(choice['text'], width=120)  # Slightly narrower for choices
                # Indent all lines after the first one for better readability
                lines = wrapped_choice.split('\n')
                if len(lines) > 1:
                    indented_text = lines[0] + '\n' + '\n'.join(['   ' + line for line in lines[1:]])
                    readable_output.append(f"{i+1}. {indented_text}")
                else:
                    readable_output.append(f"{i+1}. {wrapped_choice}")
            readable_output.append("")

        # Action taken - only show for steps that have choices
        if step.action and step.choices and len(step.choices) > 0:
            choice_index = int(step.action) - 1
            if 0 <= choice_index < len(step.choices):
                choice_text = step.choices[choice_index]['text']
                wrapped_choice = wrap_text(choice_text, width=120)
                # Indent all lines after the first one for better readability
                lines = wrapped_choice.split('\n')
                if len(lines) > 1:
                    indented_text = lines[0] + '\n' + '\n'.join(['   ' + line for line in lines[1:]])
                    readable_output.append(f"Selected option {step.action}: {indented_text}")
                else:
                    readable_output.append(f"Selected option {step.action}: {wrapped_choice}")
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
                        wrapped_reasoning = wrap_text(reasoning, width=120)
                        # Indent all lines after the first one for better readability
                        lines = wrapped_reasoning.split('\n')
                        if len(lines) > 1:
                            indented_text = lines[0] + '\n' + '\n'.join(['   ' + line for line in lines[1:]])
                            readable_output.append(f"Reasoning: {indented_text}")
                        else:
                            readable_output.append(f"Reasoning: {wrapped_reasoning}")
                        readable_output.append("")

                    # Try to get analysis - handle both attribute and dictionary access
                    analysis = None
                    if isinstance(llm_response, dict) and 'analysis' in llm_response:
                        analysis = llm_response['analysis']
                    elif hasattr(llm_response, 'analysis'):
                        analysis = llm_response.analysis

                    if analysis:
                        wrapped_analysis = wrap_text(analysis, width=120)
                        # Indent all lines after the first one for better readability
                        lines = wrapped_analysis.split('\n')
                        if len(lines) > 1:
                            indented_text = lines[0] + '\n' + '\n'.join(['   ' + line for line in lines[1:]])
                            readable_output.append(f"Analysis: {indented_text}")
                        else:
                            readable_output.append(f"Analysis: {wrapped_analysis}")
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
