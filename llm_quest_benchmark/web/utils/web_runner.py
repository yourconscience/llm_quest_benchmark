"""Web-specific quest runner utilities"""
import logging
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
import os
import json
import traceback
import uuid
from pathlib import Path

from flask import current_app, request
import sqlalchemy
from sqlalchemy.exc import SQLAlchemyError

from llm_quest_benchmark.core.runner import QuestRunner, run_quest_with_timeout
from llm_quest_benchmark.agents.base import QuestPlayer
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.dataclasses.state import AgentState
from llm_quest_benchmark.dataclasses.config import AgentConfig
from llm_quest_benchmark.utils.choice_mapper import ChoiceMapper
from llm_quest_benchmark.environments.qm import QMPlayerEnv
from ..models.database import db, Run, Step
from .errors import validate_run, validate_choice, RunNotFoundError, RunCompletedError
from llm_quest_benchmark.constants import DEFAULT_QUEST_TIMEOUT

logger = logging.getLogger(__name__)

def run_quest_with_db_logging(
    quest_path: str,
    agent: QuestPlayer,
    run_record: Run,
    timeout: int = DEFAULT_QUEST_TIMEOUT,
    debug: bool = False,
    request = None
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

    def step_callback(event: str, data: Any) -> None:
        """Callback for each step of the quest"""
        nonlocal timeout_occurred

        if event == "timeout":
            timeout_occurred = True
            if debug:
                logger.debug("Timeout callback received")
            return

        if event == "game_state" and isinstance(data, AgentState):
            steps.append(data)
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
        elif outcome is not None:
            run_record.outcome = 'SUCCESS' if outcome == QuestOutcome.SUCCESS else 'FAILURE'
    else:
        # Explicitly set end_time to None for initialization
        run_record.end_time = None

    # Commit all database changes at once
    db.session.commit()

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
        from llm_quest_benchmark.dataclasses.response import LLMResponse

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