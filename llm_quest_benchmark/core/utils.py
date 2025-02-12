"""Common utilities for llm-quest-benchmark"""
import os
import signal
import logging
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.logging import RichHandler


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


class LogManager:
    """Centralized logging configuration"""
    def __init__(self, name: str = "llm-quest"):
        # Set up logging with rich handler
        logging.basicConfig(
            level="INFO",
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler(rich_tracebacks=True)]
        )
        self.log = logging.getLogger(name)

        # Set transformers logging level
        os.environ["TRANSFORMERS_VERBOSITY"] = "error"

    def setup(self, log_level: str) -> None:
        """Configure logging based on the specified level"""
        numeric_level = getattr(logging, log_level.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError(f"Invalid log level: {log_level}")

        self.log.setLevel(numeric_level)
        if log_level.upper() == "DEBUG":
            # Create logs directory if it doesn't exist
            log_dir = Path("logs")
            log_dir.mkdir(exist_ok=True)

            # Add file handler for debug logging
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            debug_handler = logging.FileHandler(log_dir / f"llm_quest_{timestamp}.log")
            debug_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            debug_handler.setFormatter(formatter)
            self.log.addHandler(debug_handler)
            self.log.debug("Debug logging enabled")

    def get_logger(self):
        """Get the configured logger"""
        return self.log