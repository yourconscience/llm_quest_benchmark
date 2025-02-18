"""Quest runner implementation with improved logging and error handling"""
import logging
from typing import Optional, Dict, Any, Type
import json
from pathlib import Path
from datetime import datetime

from llm_quest_benchmark.constants import DEFAULT_MODEL, DEFAULT_LANG, DEFAULT_TEMPLATE, DEFAULT_TEMPERATURE
from llm_quest_benchmark.agents.base import QuestPlayer
from llm_quest_benchmark.agents.llm_agent import LLMAgent as LLMAgentClass
from llm_quest_benchmark.agents.agent_factory import create_agent
from llm_quest_benchmark.environments.qm import QMPlayerEnv
from llm_quest_benchmark.renderers.terminal import TerminalRenderer
from llm_quest_benchmark.renderers.prompt_renderer import PromptRenderer
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.core.logging import QuestLogger


def run_quest_with_timeout(
    quest_path: str,
    model: str,
    template: str = DEFAULT_TEMPLATE,
    temperature: float = DEFAULT_TEMPERATURE,
    timeout_seconds: int = 60,
    debug: bool = False,
    skip_single: bool = False,
    headless: bool = True
) -> Dict[str, Any]:
    """Run a single quest with timeout and parameters

    Args:
        quest_path (str): Path to quest file
        model (str): Model identifier (e.g. 'gpt-4o', 'random_choice')
        template (str, optional): Prompt template name. Defaults to DEFAULT_TEMPLATE.
        temperature (float, optional): Temperature for LLM sampling. Defaults to DEFAULT_TEMPERATURE.
        timeout_seconds (int, optional): Timeout in seconds. Defaults to 60.
        debug (bool, optional): Enable debug mode. Defaults to False.
        skip_single (bool, optional): Auto-select single choices. Defaults to False.
        headless (bool, optional): Run without terminal UI. Defaults to True.

    Returns:
        Dict[str, Any]: Result dictionary with quest outcome and metrics
    """
    quest_name = Path(quest_path).name
    result = {
        'quest': quest_name,
        'model': model,
        'template': template,
        'temperature': temperature,
        'outcome': QuestOutcome.ERROR.name,  # Store as string
        'error': None,
        'timestamp': datetime.now().isoformat(),
        'steps': []  # Store detailed steps
    }

    logger = logging.getLogger(__name__)
    if debug:
        logger.setLevel(logging.DEBUG)

    try:
        logger.info(f"Starting quest {quest_name} with model {model}")

        # Create quest runner with logging
        runner = QuestRunner(headless=True)  # Always headless for benchmark
        runner.initialize(
            quest=quest_path,
            model=model,
            language=DEFAULT_LANG,
            debug=debug,
            headless=True,
            template=template,
            skip_single=skip_single,
            temperature=temperature,
        )

        # Run quest and collect outcome
        outcome = runner.run()
        result['outcome'] = outcome.name

        # Collect detailed metrics from quest logger
        if runner.quest_logger:
            result['steps'] = runner.quest_logger.get_log_entries()

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        logger.error(f"Quest {quest_name} failed with error: {error_msg}")
        result['error'] = error_msg

    return result


class QuestRunner:
    """Manages quest execution with logging and metrics"""
    def __init__(self, logger: Optional[logging.Logger] = None, headless: bool = False):
        self.logger = logger or logging.getLogger(__name__)
        self.env = None
        self.agent = None
        self.terminal = None if headless else TerminalRenderer()
        self.prompt_renderer = None  # Initialize in initialize()
        self.quest_logger = None
        self.step_count = 0

    def initialize(
        self,
        quest: str,
        model: str = DEFAULT_MODEL,
        language: str = DEFAULT_LANG,
        debug: bool = False,
        headless: bool = False,
        template: str = DEFAULT_TEMPLATE,
        skip_single: bool = False,
        temperature: float = DEFAULT_TEMPERATURE
    ) -> None:
        """Initialize all components needed for quest execution"""
        self.logger.debug("Initializing environment...")
        self.env = QMPlayerEnv(quest, language=language, debug=debug)

        self.logger.debug("Initializing agent...")
        self.agent = create_agent(
            model=model,
            debug=debug,
            template=template,
            skip_single=skip_single,
            temperature=temperature
        )
        self.logger.info(f"Using agent: {self.agent.__class__.__name__}")

        self.logger.info(f"Using language: {language}")

        # Initialize prompt renderer
        self.prompt_renderer = PromptRenderer(self.env, template=template)

        # Initialize unified logger
        self.quest_logger = QuestLogger(
            debug=debug,
            is_llm=isinstance(self.agent, LLMAgentClass),
            model=model,
            template=template
        )
        self.quest_logger.set_quest_file(quest)

        # Initialize terminal renderer if not headless
        self.terminal = None if headless else TerminalRenderer()

    def run(self) -> QuestOutcome:
        """Run the quest until completion or error

        Returns:
            QuestOutcome: The final outcome of the quest
        """
        if not self.env or not self.agent:
            self.logger.error("Runner not initialized!")
            return QuestOutcome.ERROR

        try:
            # Get initial state
            observation = self.env.reset()
            if self.terminal:
                self.terminal.render_game_state(self.env.state)

            while True:
                self.step_count += 1

                # Get agent's action
                prompt = self.prompt_renderer.render_action_prompt(observation, self.env.state['choices'])
                action = self.agent.get_action(observation, self.env.state['choices'])

                # Get full LLM response if available
                llm_response = None
                if isinstance(self.agent, LLMAgentClass) and hasattr(self.agent, 'history') and len(self.agent.history) > 0:
                    llm_response = self.agent.history[-1].__dict__ if hasattr(self.agent.history[-1], '__dict__') else self.agent.history[-1]

                # Take action in environment
                observation, reward, done, info = self.env.step(action)

                # Add to history and log
                self.prompt_renderer.add_to_history(self.env.state)
                if self.quest_logger:
                    self.quest_logger.log_step(
                        step=self.step_count,
                        state=observation,
                        choices=self.env.state['choices'],
                        prompt=prompt,
                        response=action,
                        reward=reward,
                        metrics=info,
                        llm_response=llm_response
                    )

                # Optional terminal rendering
                if self.terminal:
                    self.terminal.render_game_state(self.env.state)

                if done:
                    # Quest completed
                    final_reward = reward if isinstance(reward, (int, float)) else reward.get(0, 0)
                    if final_reward > 0:
                        self.logger.info("Quest completed successfully!")
                        return QuestOutcome.SUCCESS
                    else:
                        self.logger.info("Quest failed.")
                        return QuestOutcome.FAILURE

        except Exception as e:
            self.logger.exception("Error during quest execution")
            return QuestOutcome.ERROR

    def _format_prompt(self, observation: str, choices: list) -> str:
        """Format the prompt that will be sent to the agent"""
        return f"""Observation:
{observation}

Available actions:
{json.dumps(choices, indent=2)}

Choose your action (respond with just the number):"""


def run_quest(
    quest: str,
    model: str = DEFAULT_MODEL,
    language: str = DEFAULT_LANG,
    debug: bool = False,
    headless: bool = False,
    template: str = DEFAULT_TEMPLATE,
    skip_single: bool = False,
    temperature: float = DEFAULT_TEMPERATURE,
) -> QuestOutcome:
    """Convenience function to run a quest with minimal setup
    Returns:
        QuestOutcome: The final outcome of the quest
    """
    runner = QuestRunner(headless=headless)
    runner.initialize(
        quest=quest,
        model=model,
        language=language,
        debug=debug,
        headless=headless,
        template=template,
        skip_single=skip_single,
        temperature=temperature,
    )
    return runner.run()