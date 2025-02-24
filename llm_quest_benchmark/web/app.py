"""Main entry point for the web application"""
from flask import Flask, render_template, request, jsonify, redirect, url_for
from pathlib import Path
import logging
import os

# Set working directory to workspace root
workspace_root = Path(__file__).parent.parent.parent
os.chdir(str(workspace_root))

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__)

    # Configure SQLAlchemy
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{workspace_root}/instance/llm_quest.sqlite'

    # Ensure instance folder exists
    instance_path = workspace_root / 'instance'
    try:
        instance_path.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

    # Initialize database
    from .models.database import db
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

    @app.route('/')
    def index():
        return redirect(url_for('monitor.index'))

    return app

def main():
    """Run the Flask application"""
    app = create_app()
    port = 5000
    app.logger.info(f'Starting server at http://127.0.0.1:{port}')
    app.run(port=port)

if __name__ == '__main__':
    main()