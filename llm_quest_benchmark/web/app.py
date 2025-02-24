"""Main entry point for the web application"""
from flask import Flask, render_template, request, jsonify, redirect, url_for
from pathlib import Path
import logging

from llm_quest_benchmark.core.logging import LogManager

# Initialize logging
log_manager = LogManager()
logger = log_manager.get_logger()

def create_app(test_config=None):
    """Create and configure the Flask application"""
    app = Flask(__name__,
                instance_relative_config=True,
                template_folder='templates',
                static_folder='static')

    # Default configuration
    app.config.from_mapping(
        SECRET_KEY='dev',
        DATABASE=Path('metrics.db'),
    )

    if test_config is None:
        # Load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # Load the test config if passed in
        app.config.update(test_config)

    # Ensure the instance folder exists
    try:
        Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"Failed to create instance path: {e}")

    # Initialize database
    from .models.database import init_db
    init_db(app)

    # Register blueprints
    from .views.monitor import bp as monitor_bp
    from .views.benchmark import bp as benchmark_bp
    from .views.analyze import bp as analyze_bp

    app.register_blueprint(monitor_bp)
    app.register_blueprint(benchmark_bp)
    app.register_blueprint(analyze_bp)

    # Register index route
    @app.route('/')
    def index():
        return redirect(url_for('monitor.index'))

    return app

def main():
    """Run the application"""
    app = create_app()
    app.run(debug=True)

if __name__ == '__main__':
    main()