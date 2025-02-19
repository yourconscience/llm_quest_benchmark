"""Time utilities for handling timeouts"""
import signal
import sys
import math
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from contextlib import contextmanager
from typing import Any, Callable

from llm_quest_benchmark.constants import (
    DEFAULT_QUEST_TIMEOUT,
    DEFAULT_BENCHMARK_TIMEOUT_FACTOR,
    MAX_BENCHMARK_TIMEOUT
)


class CommandTimeout(Exception):
    """Raised when a command times out"""
    pass


def calculate_benchmark_timeout(
    num_quests: int,
    num_agents: int,
    num_workers: int,
    quest_timeout: int = DEFAULT_QUEST_TIMEOUT,
    safety_factor: float = DEFAULT_BENCHMARK_TIMEOUT_FACTOR
) -> int:
    """Calculate appropriate timeout for a benchmark run

    The formula accounts for:
    - Total number of quest/agent combinations
    - Number of workers (parallel execution)
    - Base quest timeout
    - Safety factor for overhead

    Args:
        num_quests: Number of quests to run
        num_agents: Number of agents to test
        num_workers: Number of parallel workers
        quest_timeout: Timeout for individual quest runs
        safety_factor: Multiplier for safety margin

    Returns:
        int: Recommended timeout in seconds, capped at MAX_BENCHMARK_TIMEOUT
    """
    # Calculate total combinations and batches
    total_combinations = num_quests * num_agents
    num_batches = math.ceil(total_combinations / num_workers)

    # Base timeout: quest_timeout * number of sequential batches
    base_timeout = quest_timeout * num_batches

    # Apply safety factor and round up
    timeout = math.ceil(base_timeout * safety_factor)

    # Cap at maximum timeout
    return min(timeout, MAX_BENCHMARK_TIMEOUT)


def run_with_timeout(func: Callable, timeout: int, *args, **kwargs) -> Any:
    """Run a function with a timeout using ThreadPoolExecutor

    Args:
        func: Function to run
        timeout: Timeout in seconds
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func

    Returns:
        Result of the function

    Raises:
        CommandTimeout: If the function times out
    """
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, *args, **kwargs)
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            future.cancel()
            raise CommandTimeout(f"Operation timed out after {timeout} seconds")


@contextmanager
def timeout(seconds: int):
    """Context manager for timing out long-running operations

    Note: This uses signal.SIGALRM which only works on Unix-like systems.
    For cross-platform support, use run_with_timeout instead.
    """
    if sys.platform == 'win32':
        raise NotImplementedError("signal.SIGALRM is not supported on Windows")

    def handler(signum, frame):
        raise CommandTimeout(f"Operation timed out after {seconds} seconds")

    # Register a function to raise the timeout error when signal received
    signal.signal(signal.SIGALRM, handler)
    signal.alarm(seconds)

    try:
        yield
    finally:
        # Disable the alarm
        signal.alarm(0)