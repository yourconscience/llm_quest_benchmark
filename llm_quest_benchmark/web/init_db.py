"""Database initialization script for the web interface"""
import logging
import os
from pathlib import Path

from flask import Flask

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set working directory to workspace root
workspace_root = Path(__file__).parent.parent.parent
os.chdir(str(workspace_root))


def init_database():
    """Initialize the database with all required tables"""
    logger.info("Initializing database...")

    # Create a minimal Flask app for database initialization
    app = Flask(__name__)

    # Configure SQLAlchemy
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{workspace_root}/instance/llm_quest.sqlite'

    # Ensure instance folder exists
    instance_path = workspace_root / 'instance'
    try:
        instance_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Instance directory created at {instance_path}")
    except OSError as e:
        logger.error(f"Failed to create instance directory: {e}")
        return False

    # Initialize database
    from llm_quest_benchmark.web.models.database import db
    db.init_app(app)

    with app.app_context():
        # Drop all tables first to ensure clean state
        logger.info("Dropping existing tables...")
        db.drop_all()

        # Create all tables
        logger.info("Creating database tables...")
        db.create_all()

        # Verify tables were created
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        logger.info(f"Created tables: {', '.join(tables)}")

        if 'runs' in tables and 'steps' in tables:
            logger.info("Database initialization successful!")
            return True
        else:
            logger.error("Database initialization failed - required tables not created")
            return False


if __name__ == "__main__":
    success = init_database()
    if success:
        logger.info("Database initialization completed successfully")
    else:
        logger.error("Database initialization failed")
