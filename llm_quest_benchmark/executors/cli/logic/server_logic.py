"""Server logic for the web interface."""
import logging
import os
import sys
from typing import Tuple

log = logging.getLogger(__name__)

def start_server(host: str, port: int, debug: bool, workers: int, production: bool) -> Tuple[bool, str]:
    """Start the web interface server.

    Args:
        host: Host to bind to
        port: Port to bind to
        debug: Whether to run in debug mode
        workers: Number of worker processes
        production: Whether to run in production mode

    Returns:
        Tuple of (success, message)
    """
    try:
        # Import here to avoid circular imports
        from llm_quest_benchmark.web.app import create_app

        app = create_app()

        if production:
            # Use gunicorn for production
            try:
                import gunicorn.app.base

                class StandaloneApplication(gunicorn.app.base.BaseApplication):
                    def __init__(self, app, options=None):
                        self.options = options or {}
                        self.application = app
                        super().__init__()

                    def load_config(self):
                        for key, value in self.options.items():
                            if key in self.cfg.settings and value is not None:
                                self.cfg.set(key.lower(), value)

                    def load(self):
                        return self.application

                options = {
                    'bind': f"{host}:{port}",
                    'workers': workers,
                    'worker_class': 'sync',
                    'timeout': 120,
                    'loglevel': 'debug' if debug else 'info',
                }

                StandaloneApplication(app, options).run()
                return True, "Server started successfully"

            except ImportError:
                log.warning("Gunicorn not installed, falling back to Flask development server")
                # Fall back to Flask development server
                app.run(host=host, port=port, debug=debug)
                return True, "Server started successfully (using Flask development server)"
        else:
            # Use Flask development server
            app.run(host=host, port=port, debug=debug)
            return True, "Server started successfully"

    except Exception as e:
        log.exception(f"Error starting server: {e}")
        return False, str(e)