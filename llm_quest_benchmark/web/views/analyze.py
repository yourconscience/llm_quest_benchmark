"""Analysis and visualization of benchmark results"""
from flask import Blueprint, render_template, jsonify
from sqlalchemy import func, case
import json
import logging

logger = logging.getLogger(__name__)

from ..models.database import db, Run, Step
from ..utils.errors import handle_errors, WebUIError

bp = Blueprint('analyze', __name__, url_prefix='/analyze')

class NoDataError(WebUIError):
    """No data available for analysis"""
    pass

@bp.route('/')
@handle_errors
def index():
    """Analysis page"""
    return render_template('analyze/index.html')

@bp.route('/summary')
@handle_errors
def summary():
    """Get summary statistics"""
    # Get overall statistics
    stats = db.session.query(
        func.count(Run.id).label('total_runs'),
        func.sum(case([(Run.outcome == 'SUCCESS', 1)], else_=0)).label('successes'),
        func.sum(case([(Run.outcome == 'FAILURE', 1)], else_=0)).label('failures')
    ).first()

    if not stats or not stats.total_runs:
        raise NoDataError("No data available. Run some quests first!")

    return jsonify({
        'success': True,
        'total_runs': stats.total_runs,
        'success_rate': float(stats.successes / stats.total_runs) if stats.total_runs > 0 else 0.0,
        'outcomes': {
            'SUCCESS': stats.successes or 0,
            'FAILURE': stats.failures or 0
        }
    })

@bp.route('/model_comparison')
@handle_errors
def model_comparison():
    """Compare performance across different models"""
    # Get model performance data
    comparison = db.session.query(
        Run.quest_name,
        func.json_extract(Run.agent_config, '$.model').label('model'),
        func.count(Run.id).label('total_runs'),
        func.sum(case([(Run.outcome == 'SUCCESS', 1)], else_=0)).label('successes')
    ).group_by(
        Run.quest_name,
        func.json_extract(Run.agent_config, '$.model')
    ).all()

    if not comparison:
        raise NoDataError("No comparison data available. Run some benchmarks first!")

    # Convert to list of dicts
    comparison_data = [{
        'quest_name': row[0],
        'model': row[1],
        'total_runs': row[2],
        'success_rate': float(row[3] / row[2]) if row[2] > 0 else 0
    } for row in comparison]

    return jsonify({
        'success': True,
        'data': comparison_data
    })

@bp.route('/step_analysis')
@handle_errors
def step_analysis():
    """Analyze step-level metrics"""
    # Get step-level metrics
    steps = db.session.query(
        Run.quest_name,
        Step.location_id,
        func.count(Step.id).label('visit_count')
    ).join(Step, Run.id == Step.run_id
    ).group_by(
        Run.quest_name,
        Step.location_id
    ).all()

    if not steps:
        raise NoDataError("No step data available. Run some quests first!")

    # Convert to list of dicts
    step_data = [{
        'quest_name': row[0],
        'location_id': row[1],
        'visit_count': row[2]
    } for row in steps]

    return jsonify({
        'success': True,
        'data': step_data
    })

@bp.route('/run/<int:run_id>/analysis')
@handle_errors
def run_analysis(run_id):
    """Get detailed analysis for a specific run"""
    run = Run.query.get_or_404(run_id)
    steps = Step.query.filter_by(run_id=run_id).order_by(Step.step).all()

    if not steps:
        raise NoDataError(f"No step data found for run {run_id}")

    # Calculate run metrics
    total_steps = len(steps)
    total_time = (run.end_time - run.start_time).total_seconds() if run.end_time else None

    # Analyze step choices and responses
    step_metrics = []
    for step in steps:
        try:
            choices = step.choices and len(json.loads(step.choices))
            step_metrics.append({
                'step': step.step,
                'location': step.location_id,
                'num_choices': choices,
                'action': step.action
            })
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON data in step {step.id}")
            continue

    analysis = {
        'success': True,
        'run_info': run.to_dict(),
        'metrics': {
            'total_steps': total_steps,
            'total_time': total_time
        },
        'step_metrics': step_metrics
    }

    return jsonify(analysis)

@bp.errorhandler(NoDataError)
def handle_no_data_error(error):
    """Handle NoDataError by returning 400 status code"""
    return jsonify({
        'success': False,
        'error': str(error)
    }), 400

@bp.errorhandler(Exception)
def handle_error(error):
    """Handle other errors by returning 400 status code"""
    logger.error(f"Error in analyze view: {error}", exc_info=True)
    return jsonify({
        'success': False,
        'error': str(error)
    }), 400