"""Main entry point for the web application"""
from flask import Flask, render_template, request, jsonify, redirect, url_for
from pathlib import Path
import logging
import os

from llm_quest_benchmark.constants import WEB_SERVER_HOST, WEB_SERVER_PORT
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
    import socket
    import subprocess
    import sys
    import time

    port = WEB_SERVER_PORT
    app = create_app()

    # Check if port is in use and kill the process if needed
    try:
        # Try to create a socket on the port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((WEB_SERVER_HOST, port))
        sock.close()

        if result == 0:  # Port is in use
            app.logger.info(f"Port {port} is already in use. Attempting to free it...")

            # Find and kill the process using the port
            if sys.platform.startswith('darwin') or sys.platform.startswith('linux'):
                # For macOS and Linux
                try:
                    # Find the process ID using the port
                    cmd = f"lsof -i :{port} -t"
                    pid = subprocess.check_output(cmd, shell=True).decode().strip()

                    if pid:
                        # Kill the process
                        app.logger.info(f"Killing process {pid} using port {port}")
                        subprocess.run(f"kill -9 {pid}", shell=True)
                        time.sleep(1)  # Give it a moment to release the port
                except subprocess.CalledProcessError:
                    app.logger.warning(f"Could not find process using port {port}")
            elif sys.platform.startswith('win'):
                # For Windows
                try:
                    # Find the process ID using the port
                    cmd = f"netstat -ano | findstr :{port}"
                    output = subprocess.check_output(cmd, shell=True).decode()
                    if output:
                        pid = output.strip().split()[-1]
                        # Kill the process
                        app.logger.info(f"Killing process {pid} using port {port}")
                        subprocess.run(f"taskkill /F /PID {pid}", shell=True)
                        time.sleep(1)  # Give it a moment to release the port
                except subprocess.CalledProcessError:
                    app.logger.warning(f"Could not find process using port {port}")
    except Exception as e:
        app.logger.error(f"Error checking port: {e}")

    app.logger.info(f'Starting server at http://{WEB_SERVER_HOST}:{port}')
    app.run(host=WEB_SERVER_HOST, port=port)

if __name__ == '__main__':
    main()