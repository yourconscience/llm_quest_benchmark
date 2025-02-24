"""Main entry point for the web application"""
from flask import Flask, render_template, request, jsonify, redirect, url_for
from pathlib import Path
import logging
import os
from llm_quest_benchmark.web.models.database import db

# Set working directory to workspace root
workspace_root = Path(__file__).parent.parent.parent
os.chdir(workspace_root)

# Set NODE_OPTIONS for OpenSSL compatibility
if 'NODE_OPTIONS' not in os.environ:
    os.environ['NODE_OPTIONS'] = '--openssl-legacy-provider'

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
        SQLALCHEMY_DATABASE_URI=f'sqlite:///{os.path.join(app.instance_path, "llm_quest.sqlite")}',
        SQLALCHEMY_TRACK_MODIFICATIONS=False
    )

    if test_config is not None:
        # Load test config if passed in
        app.config.update(test_config)

    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Initialize database
    db.init_app(app)
    with app.app_context():
        db.create_all()

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
        """Redirect root to monitor page"""
        return redirect('/monitor')

    return app

def main():
    """Run the application"""
    app = create_app()
    app.run(debug=True)

if __name__ == '__main__':
    main()