"""Time utilities"""
import signal
from contextlib import contextmanager


class CommandTimeout(Exception):
    """Raised when a command times out"""
    pass


@contextmanager
def timeout(seconds: int):
    """Context manager for timing out long-running operations"""
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