"""Server logic for the web interface."""
import logging
import os
import sys
from typing import Tuple

log = logging.getLogger(__name__)


def start_server(host: str,
                 port: int,
                 debug: bool,
                 workers: int = None,
                 production: bool = None) -> Tuple[bool, str]:
    """Start the web interface server.

    Args:
        host: Host to bind to
        port: Port to bind to
        debug: Whether to run in debug mode
        workers: Not used (kept for backward compatibility)
        production: Not used (kept for backward compatibility)

    Returns:
        Tuple of (success, message)
    """
    try:
        # Initialize the database first
        log.info("Initializing database before starting server...")
        from llm_quest_benchmark.web.init_db import init_database
        db_init_success = init_database()

        if not db_init_success:
            return False, "Database initialization failed"

        # Import here to avoid circular imports
        from llm_quest_benchmark.web.app import create_app

        app = create_app()

        # Use Flask development server
        app.run(host=host, port=port, debug=debug)
        return True, "Server started successfully"

    except Exception as e:
        log.exception(f"Error starting server: {e}")
        return False, str(e)
