"""Server logic for the web interface."""
import logging
import subprocess
from typing import Tuple

log = logging.getLogger(__name__)

def start_server(host: str, port: int, debug: bool, workers: int = None, production: bool = None) -> Tuple[bool, str]:
    """Start the web interface server.

    Args:
        host: Host to bind to
        port: Port to bind to
        debug: Whether to run in debug mode
        workers: Worker count for production mode
        production: Whether to run via gunicorn

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

        if production:
            worker_count = workers or 4
            bind = f"{host}:{port}"
            cmd = [
                "gunicorn",
                "--bind",
                bind,
                "--workers",
                str(worker_count),
                "--threads",
                "4",
                "--timeout",
                "120",
                "llm_quest_benchmark.web.app:create_app()",
            ]
            log.info("Starting production server: %s", " ".join(cmd))
            subprocess.run(cmd, check=True)
            return True, f"Production server started at http://{bind}"

        # Import here to avoid circular imports
        from llm_quest_benchmark.web.app import create_app

        app = create_app()
        app.run(host=host, port=port, debug=debug)
        return True, "Server started successfully"

    except subprocess.CalledProcessError as e:
        log.exception(f"Gunicorn failed: {e}")
        return False, str(e)
    except Exception as e:
        log.exception(f"Error starting server: {e}")
        return False, str(e)
