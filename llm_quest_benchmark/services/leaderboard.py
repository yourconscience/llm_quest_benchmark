"""Leaderboard service implementation for analyzing agent performance."""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union

from llm_quest_benchmark.core.logging import LogManager

# Initialize logger
log_manager = LogManager()
logger = log_manager.get_logger()


class LeaderboardService:
    """Service for generating leaderboard data across interfaces.

    This service handles the common logic for analyzing agent performance
    and generating leaderboard data. It can be used by both CLI and web
    interfaces, avoiding code duplication.
    """

    def __init__(self, db_connector=None):
        """Initialize the leaderboard service with a database connector.

        Args:
            db_connector: Interface for database access, can be SQLAlchemy or SQLite
                          depending on the caller (CLI or web)
        """
        self.db_connector = db_connector

    def get_leaderboard_entries(
        self,
        benchmark_id: Optional[str] = None,
        quest_type: Optional[str] = None,
        date_range: Optional[str] = None,
        agent_id: Optional[str] = None,
        memory_type: Optional[str] = None,
        tools: Optional[List[str]] = None,
        sort_by: str = "success_rate",
        sort_order: str = "desc",
    ) -> List[Dict]:
        """Generate leaderboard entries based on filtering criteria.

        Args:
            benchmark_id: Filter by benchmark ID
            quest_type: Filter by quest type/name
            date_range: Filter by date range (today, week, month)
            agent_id: Filter by specific agent
            memory_type: Filter by memory type (message_history, summary)
            tools: Filter by tools used
            sort_by: Field to sort by
            sort_order: Sort order (asc, desc)

        Returns:
            List of leaderboard entries as dictionaries
        """
        # This method will be implemented differently depending on
        # whether we're using SQLAlchemy (web) or SQLite (CLI)
        runs = self.get_filtered_runs(benchmark_id, quest_type, date_range, agent_id, memory_type,
                                      tools)

        # Group runs by agent_id and calculate statistics
        agent_stats = self._aggregate_by_agent(runs)

        # Convert to leaderboard entries
        leaderboard_entries = self._create_leaderboard_entries(agent_stats, runs)

        # Sort entries
        reverse = sort_order.lower() == "desc"
        leaderboard_entries.sort(key=lambda x: x.get(sort_by, 0), reverse=reverse)

        return leaderboard_entries

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

        This is an abstract method that should be implemented by subclasses
        for web (SQLAlchemy) and CLI (SQLite) implementations.
        """
        if self.db_connector is None:
            logger.error("No database connector provided")
            return []

        return self.db_connector.get_filtered_runs(benchmark_id, quest_type, date_range, agent_id,
                                                   memory_type, tools)

    def get_agent_detail(self, agent_id: str) -> Dict:
        """Get detailed information about a specific agent.

        Args:
            agent_id: The ID of the agent to analyze

        Returns:
            Dictionary with agent details and performance metrics
        """
        if self.db_connector is None:
            logger.error("No database connector provided")
            return {}

        # Get all runs for this agent
        runs = self.get_filtered_runs(agent_id=agent_id)

        # Get agent configuration from the most recent run
        agent_config = self._get_agent_config(agent_id, runs)

        # Calculate overall statistics
        stats = self._calculate_agent_stats(runs)

        # Calculate per-quest statistics
        quest_stats = self._calculate_quest_stats(runs)

        # Get recent runs
        recent_runs = sorted(runs, key=lambda x: x.get('start_time', ''), reverse=True)[:10]

        return {
            'agent_id': agent_id,
            'agent_config': agent_config,
            'stats': stats,
            'quest_stats': quest_stats,
            'recent_runs': recent_runs
        }

    def _aggregate_by_agent(self, runs: List[Dict]) -> Dict[str, Dict]:
        """Aggregate runs by agent ID and calculate statistics.

        Args:
            runs: List of run dictionaries

        Returns:
            Dictionary mapping agent IDs to their statistics
        """
        agent_stats = {}

        for run in runs:
            agent_id = run.get('agent_id', 'unknown')

            if agent_id not in agent_stats:
                agent_stats[agent_id] = {
                    'runs': 0,
                    'successes': 0,
                    'failures': 0,
                    'total_reward': 0,
                    'total_steps': 0,
                    'quests': set(),
                    'model': None,
                    'memory_type': None,
                    'tools': [],
                    'token_usage': 0,
                    'response_time': 0,
                    'tool_usage_count': 0,
                }

            stats = agent_stats[agent_id]
            stats['runs'] += 1
            stats['quests'].add(run.get('quest_name', 'unknown'))

            if run.get('outcome') == 'SUCCESS':
                stats['successes'] += 1
            else:
                stats['failures'] += 1

            stats['total_reward'] += run.get('reward', 0) or 0

            # Get step count - this might be handled differently for SQLAlchemy vs SQLite
            step_count = run.get('step_count', 0)
            if step_count == 0 and 'steps' in run:
                step_count = len(run['steps'])
            stats['total_steps'] += step_count

            # Track advanced metrics if available
            stats['token_usage'] += run.get('token_usage', 0) or 0
            stats['response_time'] += run.get('response_time', 0) or 0
            stats['tool_usage_count'] += run.get('tool_usage_count', 0) or 0

            # Extract agent configuration details
            if stats['model'] is None and 'agent_config' in run:
                agent_config = run['agent_config']
                if isinstance(agent_config, str):
                    try:
                        agent_config = json.loads(agent_config)
                    except json.JSONDecodeError:
                        agent_config = {}

                if isinstance(agent_config, dict):
                    stats['model'] = agent_config.get('model', 'unknown')

                    memory_config = agent_config.get('memory', {})
                    if memory_config:
                        stats['memory_type'] = memory_config.get('type', 'none')

                    stats['tools'] = agent_config.get('tools', [])

        return agent_stats

    def _create_leaderboard_entries(self, agent_stats: Dict[str, Dict],
                                    runs: List[Dict]) -> List[Dict]:
        """Create leaderboard entries from aggregated statistics.

        Args:
            agent_stats: Aggregated statistics by agent
            runs: Original list of runs (for reference)

        Returns:
            List of leaderboard entries
        """
        leaderboard_entries = []

        for agent_id, stats in agent_stats.items():
            success_rate = stats['successes'] / stats['runs'] if stats['runs'] > 0 else 0
            avg_reward = stats['total_reward'] / stats['runs'] if stats['runs'] > 0 else 0
            avg_steps = stats['total_steps'] / stats['runs'] if stats['runs'] > 0 else 0
            avg_token_usage = stats['token_usage'] / stats['runs'] if stats['runs'] > 0 and stats[
                'token_usage'] > 0 else 0
            avg_response_time = stats['response_time'] / stats['runs'] if stats[
                'runs'] > 0 and stats['response_time'] > 0 else 0

            # Calculate efficiency score
            # Higher reward with fewer steps = more efficient
            if avg_steps > 0:
                efficiency_score = (avg_reward / avg_steps) * 100
            else:
                efficiency_score = 0

            leaderboard_entries.append({
                'agent_id': agent_id,
                'model': stats['model'] or 'unknown',
                'success_rate': success_rate,
                'avg_reward': avg_reward,
                'avg_steps': avg_steps,
                'efficiency_score': efficiency_score,
                'runs_count': stats['runs'],
                'quest_count': len(stats['quests']),
                'memory_type': stats['memory_type'] or 'none',
                'tools_used': stats['tools'],
                'avg_token_usage': avg_token_usage,
                'avg_response_time': avg_response_time,
                'tool_usage_count': stats['tool_usage_count'],
            })

        return leaderboard_entries

    def _get_agent_config(self, agent_id: str, runs: List[Dict]) -> Dict:
        """Extract agent configuration from the most recent run.

        Args:
            agent_id: Agent ID to get configuration for
            runs: List of runs for this agent

        Returns:
            Agent configuration dictionary
        """
        if not runs:
            return {}

        # Sort runs by start time, most recent first
        sorted_runs = sorted(runs, key=lambda x: x.get('start_time', ''), reverse=True)

        for run in sorted_runs:
            if run.get('agent_id') == agent_id and 'agent_config' in run:
                agent_config = run['agent_config']
                if isinstance(agent_config, str):
                    try:
                        return json.loads(agent_config)
                    except json.JSONDecodeError:
                        continue
                elif isinstance(agent_config, dict):
                    return agent_config

        return {}

    def _calculate_agent_stats(self, runs: List[Dict]) -> Dict:
        """Calculate overall statistics for an agent.

        Args:
            runs: List of runs for the agent

        Returns:
            Dictionary with calculated statistics
        """
        if not runs:
            return {
                'total_runs': 0,
                'success_rate': 0,
                'avg_reward': 0,
                'avg_steps': 0,
                'efficiency_score': 0,
            }

        total_runs = len(runs)
        successes = sum(1 for run in runs if run.get('outcome') == 'SUCCESS')
        success_rate = successes / total_runs if total_runs > 0 else 0

        total_reward = sum(run.get('reward', 0) or 0 for run in runs)
        avg_reward = total_reward / total_runs if total_runs > 0 else 0

        # Calculate total steps
        total_steps = 0
        for run in runs:
            step_count = run.get('step_count', 0)
            if step_count == 0 and 'steps' in run:
                step_count = len(run['steps'])
            total_steps += step_count

        avg_steps = total_steps / total_runs if total_runs > 0 else 0

        # Calculate efficiency score
        if avg_steps > 0:
            efficiency_score = (avg_reward / avg_steps) * 100
        else:
            efficiency_score = 0

        return {
            'total_runs': total_runs,
            'success_rate': success_rate,
            'avg_reward': avg_reward,
            'avg_steps': avg_steps,
            'efficiency_score': efficiency_score,
        }

    def _calculate_quest_stats(self, runs: List[Dict]) -> List[Dict]:
        """Calculate statistics per quest for an agent.

        Args:
            runs: List of runs for the agent

        Returns:
            List of dictionaries with per-quest statistics
        """
        # Group runs by quest
        quests = {}
        for run in runs:
            quest_name = run.get('quest_name', 'unknown')
            if quest_name not in quests:
                quests[quest_name] = []
            quests[quest_name].append(run)

        # Calculate statistics for each quest
        quest_stats = []
        for quest_name, quest_runs in quests.items():
            stats = self._calculate_agent_stats(quest_runs)
            quest_stats.append({
                'quest': quest_name,
                'runs': len(quest_runs),
                'success_rate': stats['success_rate'],
                'avg_reward': stats['avg_reward'],
                'avg_steps': stats['avg_steps'],
            })

        # Sort by success rate (highest first)
        quest_stats.sort(key=lambda x: x['success_rate'], reverse=True)

        return quest_stats

    @staticmethod
    def parse_date_range(date_range: str) -> tuple:
        """Parse date range string into start and end dates.

        Args:
            date_range: String like 'today', 'week', 'month'

        Returns:
            Tuple of (start_date, end_date)
        """
        now = datetime.utcnow()
        end_date = now.replace(hour=23, minute=59, second=59)

        if date_range == 'today':
            start_date = now.replace(hour=0, minute=0, second=0)
        elif date_range == 'week':
            # Start from beginning of the week (Monday)
            days_since_monday = now.weekday()
            start_date = (now - timedelta(days=days_since_monday)).replace(hour=0,
                                                                           minute=0,
                                                                           second=0)
        elif date_range == 'month':
            # Start from beginning of the month
            start_date = now.replace(day=1, hour=0, minute=0, second=0)
        else:
            # Default to all time
            start_date = datetime(1970, 1, 1)

        return start_date, end_date
