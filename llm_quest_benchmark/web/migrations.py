"""Database migrations for web interface"""
import logging
import sqlite3

logger = logging.getLogger(__name__)


def check_column_exists(conn, table, column):
    """Check if a column exists in a table"""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    columns = cursor.fetchall()
    return any(col[1] == column for col in columns)


def add_leaderboard_fields(app):
    """Add new fields for leaderboard functionality to the runs table"""
    try:
        db_path = app.config.get('DATABASE')
        if not db_path:
            logger.warning("No database path configured, skipping migrations")
            return False

        # Connect to the SQLite database
        conn = sqlite3.connect(db_path)

        # Check if the table exists
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='runs'")
        if not cursor.fetchone():
            logger.info("Runs table does not exist yet, no migration needed")
            conn.close()
            return False

        # Add response_time column if it doesn't exist
        if not check_column_exists(conn, 'runs', 'response_time'):
            logger.info("Adding response_time column to runs table")
            conn.execute("ALTER TABLE runs ADD COLUMN response_time REAL")

        # Add token_usage column if it doesn't exist
        if not check_column_exists(conn, 'runs', 'token_usage'):
            logger.info("Adding token_usage column to runs table")
            conn.execute("ALTER TABLE runs ADD COLUMN token_usage INTEGER")

        # Add tool_usage_count column if it doesn't exist
        if not check_column_exists(conn, 'runs', 'tool_usage_count'):
            logger.info("Adding tool_usage_count column to runs table")
            conn.execute("ALTER TABLE runs ADD COLUMN tool_usage_count INTEGER")

        # Add efficiency_score column if it doesn't exist
        if not check_column_exists(conn, 'runs', 'efficiency_score'):
            logger.info("Adding efficiency_score column to runs table")
            conn.execute("ALTER TABLE runs ADD COLUMN efficiency_score REAL")

        # Commit changes and close connection
        conn.commit()
        conn.close()
        logger.info("Database migration for leaderboard fields completed successfully")
        return True

    except Exception as e:
        logger.error(f"Error in database migration: {e}", exc_info=True)
        return False


def run_migrations(app):
    """Run all database migrations"""
    logger.info("Running database migrations")

    # Run all migrations in sequence
    add_leaderboard_fields(app)

    logger.info("Database migrations completed")
