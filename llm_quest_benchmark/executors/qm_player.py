"""
Interactive Space Rangers quests console player with rich terminal output
"""

import argparse
import logging
from pathlib import Path

from rich.console import Console

from llm_quest_benchmark.executors.ts_bridge.bridge import QMBridge
from llm_quest_benchmark.renderers.terminal import TerminalRenderer
from llm_quest_benchmark.metrics import MetricsLogger


def play_quest(quest_path: str, language: str = "rus", skip: bool = False, metrics: bool = False, debug: bool = False):
    """Play quest in interactive mode using QMBridge"""
    logger = logging.getLogger(__name__)
    if debug:
        logger.setLevel(logging.DEBUG)

    renderer = TerminalRenderer()
    console = Console()

    metrics_logger = MetricsLogger(auto_save=metrics) if metrics else None
    if metrics:
        metrics_logger.set_quest_file(str(quest_path))

    # Initialize bridge
    bridge = QMBridge(str(quest_path), debug=debug)
    try:
        # Start game and get initial state
        state = bridge.start_game()
        step_count = 0

        while not state.game_ended:
            step_count += 1
            if debug:
                logger.debug(f"\n=== Step {step_count} ===")
                logger.debug(bridge.get_debug_state())

            # Render current state
            renderer.render_game_state({
                'text': state.text,
                'choices': state.choices
            })

            # Auto-skip if enabled and only one choice
            if skip and len(state.choices) == 1:
                choice_num = 1
                console.print("[dim]Auto-selecting the only available choice.[/dim]")
            else:
                # Get user input
                while True:
                    try:
                        choice = console.input("[bold yellow]Enter choice number (or 'q' to quit): [/]")
                        if choice.lower() == 'q':
                            raise KeyboardInterrupt
                        if not choice.isdigit():
                            console.print("[red]Please enter a valid number[/]")
                            continue
                        choice_num = int(choice)
                        # Validate choice (will raise ValueError if invalid)
                        bridge.validate_choice(choice_num)
                        break
                    except ValueError as e:
                        console.print(f"[red]{str(e)}[/]")
                    except KeyboardInterrupt:
                        console.print("\n[yellow]Quest aborted by user[/]")
                        return

            # Take step
            try:
                state = bridge.step(choice_num)
                if metrics:
                    metrics_logger.log_step(
                        step_count,
                        {
                            'locationId': state.location_id,
                            'text': state.text,
                            'choices': state.choices,
                            'gameEnded': state.game_ended,
                            'reward': state.reward
                        },
                        action=str(choice_num),
                        reward=state.reward
                    )
            except Exception as e:
                logger.error(f"Error during step: {e}")
                if debug:
                    logger.debug(bridge.get_debug_state())
                raise

        # Game ended
        console.print("\n[bold green]Quest ended![/bold green]")
        console.print(f"Final reward: {state.reward}")

        if metrics and metrics_logger:
            saved_path = metrics_logger.save()
            if saved_path:
                console.print(f"\n[dim]Metrics saved to: {saved_path}[/dim]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Quest aborted by user[/]")
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/]")
        if debug:
            logger.exception("Detailed error:")
    finally:
        bridge.close()


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

    renderer = TerminalRenderer()
    renderer.render_title()
    play_quest(args.quest_path, args.lang, args.skip, args.metrics, args.debug)


if __name__ == "__main__":
    main()
