"""
Interactive Space Rangers quests console player with rich terminal output
"""

import argparse
import logging
from pathlib import Path

from llm_quest_benchmark.environments.qm import QMPlayerEnv
from llm_quest_benchmark.agents.human_player import HumanPlayer
from llm_quest_benchmark.metrics import MetricsLogger


def play_quest(quest_path: str, language: str = "rus", skip: bool = False, metrics: bool = False, debug: bool = False):
    """Play quest in interactive mode using QMPlayerEnv and HumanPlayer"""
    logger = logging.getLogger(__name__)
    if debug:
        logger.setLevel(logging.DEBUG)

    # Initialize environment and player
    env = QMPlayerEnv(str(quest_path), language=language, debug=debug)
    player = HumanPlayer(skip_single=skip, debug=debug)

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
                break

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
                player.on_game_end(env.state)
                break

        # Save metrics if enabled
        if metrics and metrics_logger:
            saved_path = metrics_logger.save()
            if saved_path and debug:
                logger.debug(f"Metrics saved to: {saved_path}")

    except Exception as e:
        logger.error(f"Error during quest: {str(e)}")
        if debug:
            logger.exception("Detailed error:")
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

    play_quest(args.quest_path, args.lang, args.skip, args.metrics, args.debug)


if __name__ == "__main__":
    main()
