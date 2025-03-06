"""Database connector implementations for LeaderboardService."""
import json
import logging
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union

from llm_quest_benchmark.core.logging import LogManager
from llm_quest_benchmark.services.leaderboard import LeaderboardService

# Initialize logger
log_manager = LogManager()
logger = log_manager.get_logger()


class DBConnector(ABC):
    """Abstract base class for database connectors."""

    @abstractmethod
    def get_filtered_runs(
        self,
        benchmark_id: Optional[str] = None,
        quest_type: Optional[str] = None,
        date_range: Optional[str] = None,
        agent_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        tools: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Get filtered runs based on criteria."""
        pass


class SQLiteConnector(DBConnector):
    """SQLite database connector for CLI interface."""

    def __init__(self, db_path: str):
        """Initialize with SQLite database path.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

    def get_filtered_runs(
        self,
        benchmark_id: Optional[str] = None,
        quest_type: Optional[str] = None,
        date_range: Optional[str] = None,
        agent_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        tools: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Get filtered runs based on criteria.

        Args:
            benchmark_id: Filter by benchmark ID
            quest_type: Filter by quest type/name
            date_range: Filter by date range (today, week, month)
            agent_id: Filter by specific agent
            memory_type: Filter by memory type (message_history, summary)
            tools: Filter by tools used

        Returns:
            List of run dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Build the base query
            query = """
            SELECT r.id, r.quest_name, r.quest_file, r.start_time, r.end_time,
                   r.agent_id, r.agent_config, r.outcome, r.reward, r.benchmark_id,
                   r.response_time, r.token_usage, r.tool_usage_count, r.efficiency_score
            FROM runs r
            WHERE 1=1
            """
            params = []

            # Add filters
            if benchmark_id:
                query += " AND r.benchmark_id = ?"
                params.append(benchmark_id)

            if quest_type:
                query += " AND r.quest_name LIKE ?"
                params.append(f"%{quest_type}%")

            if date_range:
                start_date, end_date = LeaderboardService.parse_date_range(date_range)
                query += " AND r.start_time BETWEEN ? AND ?"
                params.append(start_date.isoformat())
                params.append(end_date.isoformat())

            if agent_id:
                query += " AND r.agent_id = ?"
                params.append(agent_id)

            # Memory type and tools filters require parsing agent_config JSON
            # This is handled post-query because SQLite doesn't have good JSON functions

            # Execute query
            cursor.execute(query, params)

            # Process results
            runs = []
            for row in cursor.fetchall():
                run_dict = {
                    'id': row[0],
                    'quest_name': row[1],
                    'quest_file': row[2],
                    'start_time': row[3],
                    'end_time': row[4],
                    'agent_id': row[5],
                    'agent_config': row[6],
                    'outcome': row[7],
                    'reward': row[8],
                    'benchmark_id': row[9],
                    'response_time': row[10],
                    'token_usage': row[11],
                    'tool_usage_count': row[12],
                    'efficiency_score': row[13]
                }

                # Parse agent_config
                try:
                    if run_dict['agent_config']:
                        agent_config = json.loads(run_dict['agent_config'])

                        # Filter by memory type if specified
                        if memory_type and 'memory' in agent_config:
                            if agent_config['memory'].get('type') != memory_type:
                                continue

                        # Filter by tools if specified
                        if tools and 'tools' in agent_config:
                            # Check if any of the specified tools are in the agent's tools
                            if not any(tool in agent_config['tools'] for tool in tools):
                                continue
                except (json.JSONDecodeError, AttributeError):
                    # Skip filtering if unable to parse agent_config
                    pass

                # Get steps for this run
                cursor.execute(
                    """
                    SELECT step, location_id, observation, choices, action, llm_response
                    FROM steps
                    WHERE run_id = ?
                    ORDER BY step
                    """, (run_dict['id'],))

                steps = []
                for step_row in cursor.fetchall():
                    step_dict = {
                        'step': step_row[0],
                        'location_id': step_row[1],
                        'observation': step_row[2],
                        'choices': json.loads(step_row[3]) if step_row[3] else [],
                        'action': step_row[4],
                        'llm_response': json.loads(step_row[5]) if step_row[5] else None
                    }
                    steps.append(step_dict)

                run_dict['steps'] = steps
                run_dict['step_count'] = len(steps)

                runs.append(run_dict)

            return runs

        except Exception as e:
            logger.error(f"Error querying SQLite database: {e}")
            return []
        finally:
            if 'conn' in locals():
                conn.close()


class SQLAlchemyConnector(DBConnector):
    """SQLAlchemy database connector for web interface."""

    def __init__(self, db_session):
        """Initialize with SQLAlchemy session.

        Args:
            db_session: SQLAlchemy session object
        """
        self.db_session = db_session

    def get_filtered_runs(
        self,
        benchmark_id: Optional[str] = None,
        quest_type: Optional[str] = None,
        date_range: Optional[str] = None,
        agent_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        tools: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Get filtered runs based on criteria using SQLAlchemy.

        Args:
            benchmark_id: Filter by benchmark ID
            quest_type: Filter by quest type/name
            date_range: Filter by date range (today, week, month)
            agent_id: Filter by specific agent
            memory_type: Filter by memory type (message_history, summary)
            tools: Filter by tools used

        Returns:
            List of run dictionaries
        """
        try:
            # Import here to avoid circular imports
            from llm_quest_benchmark.web.models.database import Run, Step

            # Start with base query
            query = self.db_session.query(Run)

            # Apply filters
            if benchmark_id:
                query = query.filter(Run.benchmark_id == benchmark_id)

            if quest_type:
                query = query.filter(Run.quest_name.like(f"%{quest_type}%"))

            if date_range:
                start_date, end_date = LeaderboardService.parse_date_range(date_range)
                query = query.filter(Run.start_time.between(start_date, end_date))

            if agent_id:
                query = query.filter(Run.agent_id == agent_id)

            # Memory type and tools filters - harder to do in the query
            # We'll filter these after initial results

            # Execute query
            runs = query.all()

            # Filter by memory type and tools
            filtered_runs = []
            for run in runs:
                run_dict = run.to_dict()

                # Add steps
                steps = self.db_session.query(Step).filter(Step.run_id == run.id).order_by(
                    Step.step).all()
                run_dict['steps'] = [step.to_dict() for step in steps]
                run_dict['step_count'] = len(steps)

                # Filter by memory type
                if memory_type and run.agent_config:
                    agent_config = run.agent_config
                    if not isinstance(agent_config, dict):
                        continue

                    memory_config = agent_config.get('memory', {})
                    if not memory_config or memory_config.get('type') != memory_type:
                        continue

                # Filter by tools
                if tools and run.agent_config:
                    agent_config = run.agent_config
                    if not isinstance(agent_config, dict):
                        continue

                    agent_tools = agent_config.get('tools', [])
                    if not any(tool in agent_tools for tool in tools):
                        continue

                filtered_runs.append(run_dict)

            return filtered_runs

        except Exception as e:
            logger.error(f"Error querying database with SQLAlchemy: {e}")
            return []
