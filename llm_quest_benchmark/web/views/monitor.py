"""Quest runner and monitor blueprint"""
import glob
import json
import logging
import os
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, render_template, request

logger = logging.getLogger(__name__)

from llm_quest_benchmark.agents.agent_factory import create_agent, create_agent_from_id
from llm_quest_benchmark.agents.agent_manager import AgentManager
from llm_quest_benchmark.constants import (
    DEFAULT_MODEL,
    DEFAULT_QUEST_TIMEOUT,
    DEFAULT_TEMPERATURE,
    DEFAULT_TEMPLATE,
    MODEL_CHOICES,
    PROMPT_TEMPLATES_DIR,
    SYSTEM_ROLE_TEMPLATE,
)
from llm_quest_benchmark.schemas.config import AgentConfig
from llm_quest_benchmark.utils.text_processor import clean_qm_text, wrap_text

from ..models.database import Run, Step, db
from ..utils.errors import handle_errors, validate_choice, validate_model, validate_quest_file
from ..utils.web_runner import run_quest_with_db_logging, take_manual_step

# Initialize TypeScript bridge
os.environ['NODE_OPTIONS'] = '--openssl-legacy-provider'

bp = Blueprint('monitor', __name__, url_prefix='/monitor')


def get_available_quests():
    """Get list of available quests using the registry"""
    from llm_quest_benchmark.constants import QUEST_ROOT_DIRECTORY
    from llm_quest_benchmark.core.quest_registry import get_registry

    registry = get_registry()

    # Get unique quests only (filter out duplicates)
    quest_infos = registry.get_unique_quests()

    # Return paths relative to QUEST_ROOT_DIRECTORY
    quest_files = [info.relative_path for info in quest_infos]

    logger.debug(f"Found {len(quest_files)} unique quest files")
    return sorted(quest_files)


# We no longer need this function since we only use predefined agents
# def get_available_templates():
#    """Get list of available templates"""
#    pass


def get_available_agents():
    """Get list of available saved agents"""
    agent_manager = AgentManager()
    agents = agent_manager.get_all_agents()

    # Convert to list of dicts for template
    agent_list = []
    for agent_id, agent in agents.items():
        agent_dict = {
            'id': agent_id,
            'name': agent_id,
            'description': agent.description or f"{agent.model} agent",
            'model': agent.model
        }
        agent_list.append(agent_dict)

    return sorted(agent_list, key=lambda x: x['name'])


@bp.route('')
@handle_errors
def index():
    """Quest runner and monitor page"""
    logger.debug("Loading quest runner page")
    quests = get_available_quests()
    agents = get_available_agents()

    logger.debug(f"Available quests: {quests}")
    logger.debug(f"Available agents: {[a['id'] for a in agents]}")

    # Find the Diehard.qm quest in the list of quests (default to first in the list if not found)
    default_quest = next((q for q in quests if "Diehard.qm" in q), quests[0] if quests else "")

    # Create default agents if none exist
    if not agents:
        logger.info("No agents found, creating defaults")
        agent_manager = AgentManager()
        agent_manager.create_default_agents()
        agents = get_available_agents()

    # If we have multiple agents, set the default to GPT-4o
    default_agent = next((a for a in agents if "gpt-4o" in a['id'].lower()),
                         agents[0] if agents else None)
    default_agent_id = default_agent['id'] if default_agent else ""

    return render_template('monitor/index.html',
                           quests=quests,
                           saved_agents=agents,
                           default_quest=default_quest,
                           default_agent_id=default_agent_id)


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

    # If quest_name already starts with "quests/", use it as is, otherwise prepend
    if quest_name.startswith("quests/"):
        quest_path = quest_name
    else:
        quest_path = f"quests/{quest_name}"

    # Get timeout
    timeout = int(data.get('timeout', DEFAULT_QUEST_TIMEOUT))

    # Validate quest file
    validate_quest_file(quest_path)

    logger.debug(f"Quest path: {quest_path}")

    # Get the agent ID
    agent_id = data.get('agent_id')
    if not agent_id:
        return jsonify({'success': False, 'error': 'No agent ID provided'}), 400

    # Create agent from the agent ID
    logger.debug(f"Using agent: {agent_id}")

    # Create agent from saved ID
    agent = create_agent_from_id(agent_id, skip_single=True, debug=True)
    if not agent:
        return jsonify({'success': False, 'error': f'Agent {agent_id} not found'}), 404

    # Get agent configuration from agent manager
    agent_manager = AgentManager()
    agent_config = agent_manager.get_agent(agent_id)
    if not agent_config:
        return jsonify({
            'success': False,
            'error': f'Agent configuration for {agent_id} not found'
        }), 404

    # Create run record with agent_config
    run = Run(quest_file=quest_path,
              quest_name=Path(quest_name).stem,
              agent_id=agent_id,
              agent_config=agent_config.model_dump() if agent_config else {})
    db.session.add(run)
    db.session.commit()
    logger.debug(f"Run record created with ID: {run.id}")

    # Run quest and log to database
    result = run_quest_with_db_logging(quest_path=quest_path,
                                       agent=agent,
                                       run_record=run,
                                       timeout=timeout,
                                       debug=True,
                                       request=request)

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

        # If quest_name already starts with "quests/", use it as is, otherwise prepend
        if quest_name.startswith("quests/"):
            quest_path = quest_name
        else:
            quest_path = f"quests/{quest_name}"

        timeout = int(data.get('timeout', DEFAULT_QUEST_TIMEOUT))

        # Validate quest file
        validate_quest_file(quest_path)

        logger.debug(f"Quest path: {quest_path}")

        # Get the agent ID
        agent_id = data.get('agent_id')
        if not agent_id:
            return jsonify({'success': False, 'error': 'No agent ID provided'}), 400

        # Create agent from the agent ID
        logger.debug(f"Using agent: {agent_id}")

        # Create agent from saved ID
        agent = create_agent_from_id(agent_id, skip_single=True, debug=True)
        if not agent:
            return jsonify({'success': False, 'error': f'Agent {agent_id} not found'}), 404

        # Get agent configuration from agent manager
        agent_manager = AgentManager()
        agent_config = agent_manager.get_agent(agent_id)
        if not agent_config:
            return jsonify({
                'success': False,
                'error': f'Agent configuration for {agent_id} not found'
            }), 404

        # Create run record with agent_config
        run = Run(quest_file=quest_path,
                  quest_name=Path(quest_name).stem,
                  agent_id=agent_id,
                  agent_config=agent_config.model_dump() if agent_config else {})
        db.session.add(run)
        db.session.commit()
        logger.debug(f"Run record created with ID: {run.id}")

        # Run quest and log to database
        result = run_quest_with_db_logging(quest_path=quest_path,
                                           agent=agent,
                                           run_record=run,
                                           timeout=timeout,
                                           debug=True,
                                           request=request)

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
    return jsonify({'success': True, 'runs': [run.to_dict() for run in runs]})


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

    return jsonify({'success': True, 'run': run_dict, 'steps': step_dicts, 'outcome': run.outcome})


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
                wrapped_choice = wrap_text(choice['text'],
                                           width=120)  # Slightly narrower for choices
                # Indent all lines after the first one for better readability
                lines = wrapped_choice.split('\n')
                if len(lines) > 1:
                    indented_text = lines[0] + '\n' + '\n'.join(
                        ['   ' + line for line in lines[1:]])
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
                    indented_text = lines[0] + '\n' + '\n'.join(
                        ['   ' + line for line in lines[1:]])
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
                            indented_text = lines[0] + '\n' + '\n'.join(
                                ['   ' + line for line in lines[1:]])
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
                            indented_text = lines[0] + '\n' + '\n'.join(
                                ['   ' + line for line in lines[1:]])
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

    return jsonify({'success': True, 'readable_output': '\n'.join(readable_output)})


# We no longer need this endpoint since we only use predefined agents
# and don't show template content in the UI anymore
