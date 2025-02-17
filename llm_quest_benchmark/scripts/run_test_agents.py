#!/usr/bin/env python3
"""Script to run test agents on all quests in a directory"""
import os
import sys
import logging
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from typing import List, Dict, Any

from llm_quest_benchmark.core.runner import run_quest, run_quest_with_timeout
from llm_quest_benchmark.environments.state import QuestOutcome

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True  # Override any existing logging configuration
)

# Reduce verbosity of other loggers
logging.getLogger('quest').setLevel(logging.WARNING)
logging.getLogger('llm_quest_benchmark').setLevel(logging.WARNING)
logging.getLogger('llm_quest_benchmark.executors.ts_bridge').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

def run_all_quests(quest_path: str, models: List[str], timeout_seconds: int = 60, max_workers: int = 4) -> List[Dict[str, Any]]:
    """Run all quests in directory or a single quest file"""
    quest_files = []
    if os.path.isfile(quest_path):
        if quest_path.endswith('.qm'):
            quest_files = [quest_path]
    else:
        quest_files = [
            os.path.join(quest_path, f)
            for f in os.listdir(quest_path)
            if f.endswith('.qm')
        ]

    if not quest_files:
        logger.warning(f"No .qm files found in {quest_path}")
        return []

    all_tasks = []
    for quest in quest_files:
        for model in models:
            all_tasks.append((quest, model))

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_task = {
            executor.submit(run_quest_with_timeout, quest, model, timeout_seconds): (quest, model)
            for quest, model in all_tasks
        }

        # Wait for each future to complete with timeout
        for future in as_completed(future_to_task):
            quest, model = future_to_task[future]
            try:
                result = future.result(timeout=timeout_seconds)  # Use future's timeout
                results.append(result)
                status = 'SUCCESS' if result['outcome'] == QuestOutcome.SUCCESS else 'FAILED'
                error_msg = f" (Error: {result['error']})" if result['error'] else ""
                logger.info(f"{result['quest']} - {model}: {status}{error_msg}")
            except TimeoutError:
                logger.error(f"Quest {quest} with {model} timed out after {timeout_seconds}s")
                results.append({
                    'quest': Path(quest).name,
                    'model': model,
                    'outcome': QuestOutcome.ERROR,
                    'error': f'Timeout after {timeout_seconds}s'
                })
            except Exception as e:
                logger.error(f"Quest {quest} with {model} failed: {e}")
                results.append({
                    'quest': Path(quest).name,
                    'model': model,
                    'outcome': QuestOutcome.ERROR,
                    'error': str(e)
                })

    return results

def main():
    parser = argparse.ArgumentParser(description='Run test agents on all quests in a directory or a single quest file')
    parser.add_argument('quest_path', help='Path to a .qm file or directory containing .qm quest files')
    parser.add_argument('--models', nargs='+', default=['first_choice', 'random_choice'],
                      help='Models to test (default: first_choice random_choice)')
    parser.add_argument('--timeout', type=int, default=60,
                      help='Timeout in seconds for each quest (default: 60)')
    parser.add_argument('--workers', type=int, default=4,
                      help='Number of parallel workers (default: 4)')
    args = parser.parse_args()

    logger.info(f"Running quests from {args.quest_path}")
    logger.info(f"Using models: {args.models}")

    results = run_all_quests(
        args.quest_path,
        args.models,
        timeout_seconds=args.timeout,
        max_workers=args.workers
    )

    # Print summary
    print("\nResults Summary:")
    print("=" * 80)
    for model in args.models:
        model_results = [r for r in results if r['model'] == model]
        success = len([r for r in model_results if r['outcome'] == QuestOutcome.SUCCESS])
        failed = len([r for r in model_results if r['outcome'] == QuestOutcome.FAILURE])
        error = len([r for r in model_results if r['outcome'] == QuestOutcome.ERROR])
        total = len(model_results)

        print(f"\nModel: {model}")
        print(f"Total quests: {total}")
        print(f"Success: {success} ({success/total*100:.1f}%)")
        print(f"Failed: {failed} ({failed/total*100:.1f}%)")
        print(f"Error: {error} ({error/total*100:.1f}%)")

    # List errors if any
    errors = [r for r in results if r['error']]
    if errors:
        print("\nErrors encountered:")
        print("=" * 80)
        for r in errors:
            print(f"{r['quest']} - {r['model']}: {r['error']}")

if __name__ == '__main__':
    main()