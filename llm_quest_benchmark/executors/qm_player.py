"""
Interactive Space Rangers quests console player with rich terminal output
"""

import argparse
import logging
from pathlib import Path
from typing import Optional

from llm_quest_benchmark.environments.qm import QMPlayerEnv
from llm_quest_benchmark.agents.human_player import HumanPlayer
from llm_quest_benchmark.metrics import MetricsLogger
from llm_quest_benchmark.environments.state import QuestOutcome


def play_quest(
    quest_path: str,
    language: str = "rus",
    player: Optional[HumanPlayer] = None,
    skip_single: bool = False,
    metrics: bool = False,
    debug: bool = False
) -> QuestOutcome:
    """Play quest in interactive mode using QMPlayerEnv and HumanPlayer

    Args:
        quest_path: Path to quest file
        language: Quest language (rus or eng)
        player: Optional player instance (defaults to HumanPlayer)
        skip_single: Auto-select single choices (only used if player not provided)
        metrics: Enable metrics logging
        debug: Enable debug logging

    Returns:
        QuestOutcome indicating success/failure/error
    """
    logger = logging.getLogger(__name__)
    if debug:
        logger.setLevel(logging.DEBUG)

    # Initialize environment and player
    env = QMPlayerEnv(str(quest_path), language=language, debug=debug)
    if player is None:
        player = HumanPlayer(skip_single=skip_single, debug=debug)

    # Setup metrics if enabled
    metrics_logger = MetricsLogger(auto_save=metrics) if metrics else None
    if metrics:
        metrics_logger.set_quest_file(str(quest_path))

    try:
        # Start game
        observation = env.reset()
        player.on_game_start()
        step_count = 0

        while True:
            step_count += 1
            if debug:
                logger.debug(f"\n=== Step {step_count} ===")

            # Get player's action
            try:
                action = player.get_action(observation, env.state['choices'])
            except KeyboardInterrupt:
                logger.info("Quest aborted by user")
                return QuestOutcome.ERROR

            # Take step in environment
            observation, reward, done, info = env.step(action)

            # Log metrics if enabled
            if metrics:
                metrics_logger.log_step(
                    step_count,
                    env.state,
                    action=action,
                    reward=reward
                )

            if done:
                # Determine outcome based on reward
                final_reward = reward if isinstance(reward, (int, float)) else reward.get(0, 0)
                if final_reward > 0:
                    logger.info("Quest completed successfully!")
                    return QuestOutcome.SUCCESS
                else:
                    logger.info("Quest failed.")
                    return QuestOutcome.FAILURE

        # Save metrics if enabled
        if metrics and metrics_logger:
            saved_path = metrics_logger.save()
            if saved_path and debug:
                logger.debug(f"Metrics saved to: {saved_path}")

    except Exception as e:
        logger.error(f"Error during quest: {str(e)}")
        if debug:
            logger.exception("Detailed error:")
        return QuestOutcome.ERROR
    finally:
        env.close()


def main():
    parser = argparse.ArgumentParser(
        description="Run Space Rangers quest interactively",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("quest_path", help="Path to the .qm file")
    parser.add_argument(
        "--lang",
        choices=["rus", "eng"],
        default="rus",
        help="Language for quest text (default: rus)",
    )
    parser.add_argument(
        "--skip",
        action="store_true",
        help="Auto-select single choices",
    )
    parser.add_argument(
        "--metrics",
        action="store_true",
        help="Enable metrics collection",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    play_quest(args.quest_path, args.lang, skip_single=args.skip, metrics=args.metrics, debug=args.debug)


if __name__ == "__main__":
    main()
