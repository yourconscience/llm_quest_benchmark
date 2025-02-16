"""
Interactive Space Rangers quests console player with rich terminal output
"""

import argparse
import logging
from typing import Optional

from llm_quest_benchmark.environments.qm import QMPlayerEnv
from llm_quest_benchmark.agents.human_player import HumanPlayer
from llm_quest_benchmark.core.logging import QuestLogger
from llm_quest_benchmark.environments.state import QuestOutcome
from llm_quest_benchmark.constants import DEFAULT_LANG


def play_quest(
    quest: str,
    player: Optional[HumanPlayer] = None,
    skip_single: bool = False,
    debug: bool = False
) -> QuestOutcome:
    """Play quest in interactive mode using QMPlayerEnv and HumanPlayer

    Args:
        quest: Path to quest file
        player: Optional player instance (defaults to HumanPlayer)
        skip_single: Auto-select single choices (only used if player not provided)
        debug: Enable debug logging

    Returns:
        QuestOutcome indicating success/failure/error
    """
    logger = logging.getLogger(__name__)
    if debug:
        logger.setLevel(logging.DEBUG)

    # Initialize environment and player
    env = QMPlayerEnv(quest, language=DEFAULT_LANG, debug=debug)
    if player is None:
        player = HumanPlayer(skip_single=skip_single, debug=debug)

    # Setup metrics logging
    quest_logger = QuestLogger(debug=debug, is_llm=False)
    quest_logger.set_quest_file(quest)

    try:
        # Get initial state
        observation = env.reset()
        state = env.state

        while True:
            # Get player's action
            action = player.get_action(observation, state['choices'])

            # Take action in environment
            observation, reward, done, info = env.step(action)
            state = env.state

            # Log metrics
            quest_logger.log_step(
                step=len(quest_logger.steps) + 1,
                state=observation,
                choices=state['choices'],
                prompt="",  # No prompt for human player
                response=action,
                reward=reward,
                metrics=info
            )

            if done:
                # Quest completed
                final_reward = reward if isinstance(reward, (int, float)) else reward.get(0, 0)
                if final_reward > 0:
                    logger.info("Quest completed successfully!")
                    return QuestOutcome.SUCCESS
                else:
                    logger.info("Quest failed.")
                    return QuestOutcome.FAILURE

    except KeyboardInterrupt:
        logger.info("\nQuest interrupted by user.")
        return QuestOutcome.ERROR

    except Exception as e:
        logger.exception(f"Error during quest execution: {e}")
        return QuestOutcome.ERROR


def main():
    parser = argparse.ArgumentParser(
        description="Run Space Rangers quest interactively",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("quest", help="Path to the .qm file")
    parser.add_argument(
        "--skip",
        action="store_true",
        help="Auto-select single choices",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    play_quest(args.quest, skip_single=args.skip, debug=args.debug)


if __name__ == "__main__":
    main()
