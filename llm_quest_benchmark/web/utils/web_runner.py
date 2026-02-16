"""Web-specific quest runner utilities"""
import logging
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
import os
import json
import traceback
import uuid
from pathlib import Path

from flask import current_app, request, Flask
import sqlalchemy
from sqlalchemy.exc import SQLAlchemyError

from llm_quest_benchmark.core.runner import QuestRunner, run_quest_with_timeout
from llm_quest_benchmark.agents.base import QuestPlayer
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.schemas.state import AgentState
from llm_quest_benchmark.schemas.config import AgentConfig
from llm_quest_benchmark.utils.choice_mapper import ChoiceMapper
from llm_quest_benchmark.environments.qm import QMPlayerEnv
from ..models.database import db, Run, Step, RunEvent
from .errors import validate_run, validate_choice, RunNotFoundError, RunCompletedError
from llm_quest_benchmark.constants import DEFAULT_QUEST_TIMEOUT

logger = logging.getLogger(__name__)

def run_quest_with_db_logging(
    quest_path: str,
    agent: QuestPlayer,
    run_record: Run,
    timeout: int = DEFAULT_QUEST_TIMEOUT,
    debug: bool = False,
    request = None,
    event_sink: Optional[Callable[[str, Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """Run a quest and log results to database.

    Args:
        quest_path: Path to quest file
        agent: Agent to use for quest
        run_record: Run record to update
        timeout: Timeout in seconds
        debug: Whether to enable debug logging
        request: The Flask request object (optional)

    Returns:
        Dict with run results
    """
    steps = []
    timeout_occurred = False

    # Get the current Flask app
    app = current_app._get_current_object()

    def _emit_event(event_name: str, payload: Dict[str, Any]) -> None:
        if event_sink:
            try:
                event_sink(event_name, payload)
            except Exception as e:
                logger.error(f"Error in event sink: {e}")

    def _serialize_step_event(data: AgentState) -> Dict[str, Any]:
        choices = data.choices or []
        action_raw = data.action
        selected_map: Dict[str, str] = {}
        action_idx: Optional[int] = None
        try:
            action_idx = int(action_raw) if action_raw is not None else None
        except (TypeError, ValueError):
            action_idx = None

        if action_idx is not None and 1 <= action_idx <= len(choices):
            selected_map[str(action_idx)] = choices[action_idx - 1].get("text", "")

        llm_payload: Dict[str, Any] = {}
        if data.llm_response is not None:
            if hasattr(data.llm_response, "to_dict"):
                llm_payload = data.llm_response.to_dict()
            elif isinstance(data.llm_response, dict):
                llm_payload = data.llm_response

        llm_decision = {
            "analysis": llm_payload.get("analysis"),
            "reasoning": llm_payload.get("reasoning"),
            "is_default": bool(llm_payload.get("is_default", False)),
            "parse_fallback_used": bool(llm_payload.get("is_default", False)),
            "choice": selected_map,
        }
        usage = {
            "prompt_tokens": int(llm_payload.get("prompt_tokens") or 0),
            "completion_tokens": int(llm_payload.get("completion_tokens") or 0),
            "total_tokens": int(llm_payload.get("total_tokens") or 0),
            "estimated_cost_usd": llm_payload.get("estimated_cost_usd"),
        }
        indexed_choices = {
            str(i): c.get("text", "")
            for i, c in enumerate(choices, start=1)
        }
        return {
            "observation": data.observation,
            "choices": indexed_choices,
            "selected_action": action_idx,
            "llm_decision": llm_decision,
            "usage": usage,
        }

    def step_callback(event: str, data: Any) -> None:
        """Callback for each step of the quest"""
        nonlocal timeout_occurred

        if event == "timeout":
            timeout_occurred = True
            if debug:
                logger.debug("Timeout callback received")
            with app.app_context():
                try:
                    timeout_event = RunEvent(
                        run_id=run_record.id,
                        event_type="timeout",
                        payload={"message": f"Quest timed out after {timeout} seconds"},
                    )
                    db.session.add(timeout_event)
                    db.session.commit()
                except Exception as e:
                    logger.error(f"Error logging timeout event: {e}")
            _emit_event("timeout", {"run_id": run_record.id, "timeout": timeout})
            return

        if event == "game_state" and isinstance(data, AgentState):
            steps.append(data)
            # Use Flask application context to ensure database operations work
            with app.app_context():
                try:
                    step = Step(
                        run_id=run_record.id,
                        step=data.step,
                        location_id=data.location_id,
                        observation=data.observation,
                        choices=data.choices,
                        action=data.action,
                        llm_response=data.llm_response.to_dict() if data.llm_response else None
                    )
                    db.session.add(step)
                    step_event_payload = _serialize_step_event(data)
                    run_event = RunEvent(
                        run_id=run_record.id,
                        event_type="step",
                        step=data.step,
                        location_id=data.location_id,
                        payload=step_event_payload,
                    )
                    db.session.add(run_event)
                    db.session.commit()
                    _emit_event(
                        "step",
                        {
                            "run_id": run_record.id,
                            "event_id": run_event.id,
                            "step": data.step,
                            "location_id": data.location_id,
                        },
                    )
                except Exception as e:
                    logger.error(f"Error in step callback: {e}")
                    logger.error(traceback.format_exc())

    # Get agent_id directly from the agent
    agent_id = getattr(agent, 'agent_id', None)
    if agent_id:
        # Update the agent_id in the run record
        run_record.agent_id = agent_id
        db.session.commit()
        
    # Create AgentConfig from run_record.agent_config
    agent_config = None
    if run_record.agent_config:
        agent_config = AgentConfig(**run_record.agent_config)

    # Run quest using the runner
    outcome = run_quest_with_timeout(
        quest_path=quest_path,
        agent=agent,
        timeout=timeout,
        agent_config=agent_config,
        debug=debug,
        callbacks=[step_callback]
    )

    # Check if this is just initialization (only getting the first step)
    # This is determined by checking if we're using the 'init_quest_route' endpoint
    is_initialization = request and request.endpoint == 'monitor.init_quest_route'

    # Only set end_time and outcome if this is not initialization
    if not is_initialization:
        run_record.end_time = datetime.utcnow()
        if outcome is None and timeout_occurred:
            run_record.outcome = 'TIMEOUT'
            run_record.reward = 0.0
        elif outcome is not None:
            if outcome == QuestOutcome.SUCCESS:
                run_record.outcome = 'SUCCESS'
            elif outcome == QuestOutcome.FAILURE:
                run_record.outcome = 'FAILURE'
            elif outcome == QuestOutcome.TIMEOUT:
                run_record.outcome = 'TIMEOUT'
            elif outcome == QuestOutcome.ERROR:
                run_record.outcome = 'ERROR'
            else:
                run_record.outcome = 'FAILURE'
            run_record.reward = 1.0 if run_record.outcome == 'SUCCESS' else 0.0
    else:
        # Explicitly set end_time to None for initialization
        run_record.end_time = None

    # Commit all database changes at once
    db.session.commit()

    if not is_initialization:
        with app.app_context():
            try:
                outcome_event = RunEvent(
                    run_id=run_record.id,
                    event_type="outcome",
                    step=len(steps) if steps else None,
                    location_id=steps[-1].location_id if steps else None,
                    payload={
                        "outcome": run_record.outcome,
                        "step_count": len(steps),
                        "timeout": bool(timeout_occurred),
                    },
                )
                db.session.add(outcome_event)
                db.session.commit()
                _emit_event(
                    "outcome",
                    {
                        "run_id": run_record.id,
                        "event_id": outcome_event.id,
                        "outcome": run_record.outcome,
                        "step_count": len(steps),
                    },
                )
            except Exception as e:
                logger.error(f"Error logging outcome event: {e}")

    # Get the current state (first step) for the response
    current_state = steps[0].to_dict() if steps else None

    # Extract quest name from path
    quest_name = Path(quest_path).stem

    # Return result
    return {
        'success': True,
        'run_id': run_record.id,
        'quest_file': quest_path,
        'quest_name': quest_name,
        'steps': [step.to_dict() for step in steps],
        'state': current_state,
        'outcome': run_record.outcome
    }


class ManualChoiceAgent(QuestPlayer):
    """Agent that always returns a predefined choice"""

    def __init__(self, choice: int):
        self.choice = choice
        self.last_response = None

    def get_action(self, observation: str, choices: List[Dict[str, Any]]) -> int:
        from llm_quest_benchmark.schemas.response import LLMResponse

        self.last_response = LLMResponse(
            action=self.choice,
            is_default=False,
            reasoning='Manual user selection',
            analysis=None
        )
        return self.choice

    def get_last_response(self):
        return self.last_response

    def on_game_end(self, state: Dict[str, Any]) -> None:
        pass

    def __str__(self) -> str:
        return f"ManualChoiceAgent(choice={self.choice})"


class ReplayQuestRunner(QuestRunner):
    """Quest runner that replays previous steps before taking a new action."""

    def run(self, quest_path: str, previous_steps: List[Step]) -> Optional[QuestOutcome]:
        """Run quest with replay of previous steps."""
        if not self.agent:
            self.logger.error("No agent initialized!")
            return QuestOutcome.ERROR

        try:
            # Initialize environment and replay previous steps
            self.initialize(quest_path)
            observation = self.env.reset()

            # Replay previous steps
            if previous_steps:
                for step in previous_steps:
                    if step.action:
                        try:
                            action = int(step.action)
                            self.env.step(action)
                        except (ValueError, TypeError):
                            self.logger.warning(f"Invalid action in step replay: {step.action}")

            # Set step count based on previous steps
            self.step_count = len([s for s in previous_steps if s.action])

            # Check if there are any choices available
            if not self.env.state['choices']:
                self.logger.debug("No more choices available - quest ended")
                return QuestOutcome.FAILURE

            # Get agent's action and validate it
            action = self.agent.get_action(observation, self.env.state['choices'])
            choice_mapper = ChoiceMapper(self.env.state['choices'])
            if action not in choice_mapper:
                self.logger.error(f"Invalid choice: {action}")
                return QuestOutcome.ERROR

            # Take action in environment
            observation, done, success, info = self.env.step(action)

            # Create agent state for callback
            agent_state = AgentState(
                step=self.step_count + 1,
                location_id=self.env.state['location_id'],
                observation=observation,
                choices=self.env.state['choices'],
                action=str(action),
                llm_response=self.agent.get_last_response()
            )
            self._notify_callbacks("game_state", agent_state)

            return QuestOutcome.SUCCESS if done and success else QuestOutcome.FAILURE if done else None

        except Exception as e:
            self.logger.error(f"Error in replay run: {e}", exc_info=True)
            return QuestOutcome.ERROR
        finally:
            if hasattr(self, 'env') and self.env:
                self.env.close()


def take_manual_step(
    run_id: int,
    choice_num: int,
    debug: bool = False
) -> Dict[str, Any]:
    """Take a manual step in an existing quest run."""
    logger.info(f"Taking manual step for run {run_id} with choice {choice_num}")

    try:
        # Validate run exists and is not completed
        run = validate_run(run_id)
        logger.info(f"Run validated: {run.id}, completed: {run.end_time is not None}")

        # Extract quest name from quest_file
        quest_name = Path(run.quest_file).stem if run.quest_file else run.quest_name or "Unknown"

        # Get the latest step
        latest_step = Step.query.filter_by(run_id=run_id).order_by(Step.step.desc()).first()
        if not latest_step:
            logger.error(f"No steps found for run {run_id}")
            return {'success': False, 'error': 'No steps found for this run'}

        # Validate choice
        choices = latest_step.choices
        logger.debug(f"Validating choice {choice_num} against {choices}")
        validate_choice(choice_num, choices)

        # Update the latest step with the chosen action
        latest_step.action = str(choice_num)
        db.session.commit()
        logger.debug(f"Updated step {latest_step.step} with action {latest_step.action}")

        # Take the next step in the quest
        quest_path = run.quest_file
        logger.debug(f"Loading quest from {quest_path}")

        # Create QMPlayerEnv directly
        env = QMPlayerEnv(quest_path, debug=debug)

        # Get the current location
        current_location = latest_step.location_id
        logger.debug(f"Current location: {current_location}")

        # Get the chosen option
        choice_index = int(choice_num) - 1
        chosen_option = choices[choice_index]['id']
        logger.debug(f"Chosen option: {chosen_option}")

        # Initialize the environment to the current state
        env.reset()

        # Take the step
        observation, done, success, info = env.step(choice_num)
        next_location = env.state['location_id']
        next_choices = env.state['choices']
        outcome = 'SUCCESS' if done and success else 'FAILURE' if done else None
        logger.debug(f"Next location: {next_location}, Outcome: {outcome}")

        # Create a new step record
        new_step = Step(
            run_id=run_id,
            step=latest_step.step + 1,
            location_id=next_location,
            observation=observation,
            choices=next_choices,
            action=None,
            llm_response=None
        )
        db.session.add(new_step)

        # Update run record if game ended
        if outcome:
            run.end_time = datetime.now()
            run.outcome = outcome
            logger.info(f"Quest ended with outcome: {outcome}")

        db.session.commit()
        logger.debug(f"Created new step {new_step.step}")

        # Return the current state
        current_state = {
            'step': new_step.step,
            'location_id': new_step.location_id,
            'observation': new_step.observation,
            'choices': new_step.choices,
            'game_ended': outcome is not None
        }

        return {
            'success': True,
            'run_id': run.id,
            'quest_file': run.quest_file,
            'quest_name': quest_name,
            'state': current_state,
            'outcome': run.outcome
        }
    except Exception as e:
        logger.error(f"Error in take_manual_step: {str(e)}", exc_info=True)
        return {'success': False, 'error': f'Error: {str(e)}'}
