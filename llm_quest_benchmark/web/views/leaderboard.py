"""Leaderboard views for web interface."""
import json
import logging
from datetime import datetime

from flask import Blueprint, Response, jsonify, render_template, request, url_for

from llm_quest_benchmark.core.logging import LogManager
from llm_quest_benchmark.services.db_connectors import SQLAlchemyConnector
from llm_quest_benchmark.services.leaderboard import LeaderboardService
from llm_quest_benchmark.web.models.database import BenchmarkRun, Run, db

# Initialize logging
log_manager = LogManager()
logger = log_manager.get_logger()

# Create blueprint
bp = Blueprint('leaderboard', __name__, url_prefix='/leaderboard')


@bp.route('/')
def index():
    """Show leaderboard for all agents."""
    # Get filter parameters
    benchmark_id = request.args.get('benchmark', None)
    quest_type = request.args.get('quest_type', None)
    date_range = request.args.get('date_range', None)
    agent_id = request.args.get('agent_id', None)
    memory_type = request.args.get('memory_type', None)
    tool = request.args.get('tool', None)
    sort_by = request.args.get('sort', 'success_rate')
    sort_order = request.args.get('order', 'desc')

    # Process tool filter (comma-separated string to list)
    tools = None
    if tool:
        tools = [t.strip() for t in tool.split(',')]

    # Create SQLAlchemy connector
    db_connector = SQLAlchemyConnector(db.session)
    leaderboard_service = LeaderboardService(db_connector)

    # Get leaderboard entries
    entries = leaderboard_service.get_leaderboard_entries(
        benchmark_id=benchmark_id,
        quest_type=quest_type,
        date_range=date_range,
        agent_id=agent_id,
        memory_type=memory_type,
        tools=tools,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    # Get available benchmarks for filter dropdown
    benchmarks = BenchmarkRun.query.all()

    # Get unique quest names
    quest_names = db.session.query(Run.quest_name).distinct().all()
    quest_names = sorted([q[0] for q in quest_names])

    # Get unique agent IDs
    agent_ids = db.session.query(Run.agent_id).distinct().all()
    agent_ids = sorted([a[0] for a in agent_ids])

    # Prepare filter values for template
    current_filters = {
        'benchmark': benchmark_id,
        'quest_type': quest_type,
        'date_range': date_range,
        'agent_id': agent_id,
        'memory_type': memory_type,
        'tool': tool,
        'sort': sort_by,
        'order': sort_order
    }

    return render_template('leaderboard/index.html',
                           entries=entries,
                           benchmarks=benchmarks,
                           quest_names=quest_names,
                           agent_ids=agent_ids,
                           current_filters=current_filters)


@bp.route('/agent/<agent_id>')
def agent_detail(agent_id):
    """Show detailed analysis for a specific agent."""
    # Create SQLAlchemy connector
    db_connector = SQLAlchemyConnector(db.session)
    leaderboard_service = LeaderboardService(db_connector)

    # Get agent details
    details = leaderboard_service.get_agent_detail(agent_id)

    if not details or not details.get('stats'):
        return render_template('leaderboard/agent_not_found.html', agent_id=agent_id)

    agent_config = details.get('agent_config', {})
    stats = details.get('stats', {})
    quest_stats = details.get('quest_stats', [])
    recent_runs = details.get('recent_runs', [])

    return render_template('leaderboard/agent_detail.html',
                           agent_id=agent_id,
                           agent_config=agent_config,
                           stats=stats,
                           quest_stats=quest_stats,
                           recent_runs=recent_runs)


@bp.route('/api', methods=['GET'])
def leaderboard_api():
    """API endpoint for leaderboard data (for AJAX or exports)."""
    # Get filter parameters (same as index)
    benchmark_id = request.args.get('benchmark', None)
    quest_type = request.args.get('quest_type', None)
    date_range = request.args.get('date_range', None)
    agent_id = request.args.get('agent_id', None)
    memory_type = request.args.get('memory_type', None)
    tool = request.args.get('tool', None)
    sort_by = request.args.get('sort', 'success_rate')
    sort_order = request.args.get('order', 'desc')
    format_type = request.args.get('format', 'json')

    # Process tool filter (comma-separated string to list)
    tools = None
    if tool:
        tools = [t.strip() for t in tool.split(',')]

    # Create SQLAlchemy connector
    db_connector = SQLAlchemyConnector(db.session)
    leaderboard_service = LeaderboardService(db_connector)

    # Get leaderboard entries
    entries = leaderboard_service.get_leaderboard_entries(
        benchmark_id=benchmark_id,
        quest_type=quest_type,
        date_range=date_range,
        agent_id=agent_id,
        memory_type=memory_type,
        tools=tools,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    # Return based on format
    if format_type == 'csv':
        # Generate CSV
        csv_data = "Rank,Agent,Model,Success Rate,Avg Reward,Avg Steps,Efficiency,Memory,Tools,Runs\n"
        for i, entry in enumerate(entries, 1):
            # Format values
            success_pct = f"{entry['success_rate'] * 100:.1f}"
            memory = entry.get('memory_type', 'none')
            tools_str = ",".join(entry.get('tools_used', [])) or "none"

            csv_data += f"{i},{entry['agent_id']},{entry['model']},{success_pct},"
            csv_data += f"{entry['avg_reward']:.1f},{entry['avg_steps']:.1f},"
            csv_data += f"{entry['efficiency_score']:.1f},{memory},"
            csv_data += f"\"{tools_str}\",{entry['runs_count']}\n"

        # Return as CSV file
        return Response(csv_data,
                        mimetype="text/csv",
                        headers={"Content-Disposition": "attachment;filename=leaderboard.csv"})
    else:
        # Return as JSON
        return jsonify(entries)


@bp.route('/api/agent/<agent_id>', methods=['GET'])
def agent_api(agent_id):
    """API endpoint for agent details (for AJAX or exports)."""
    # Create SQLAlchemy connector
    db_connector = SQLAlchemyConnector(db.session)
    leaderboard_service = LeaderboardService(db_connector)

    # Get agent details
    details = leaderboard_service.get_agent_detail(agent_id)

    # Return as JSON
    return jsonify(details)
