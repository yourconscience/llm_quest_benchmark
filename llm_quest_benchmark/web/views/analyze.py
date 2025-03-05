"""Analysis and visualization of benchmark results"""
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, render_template, request
from sqlalchemy import case, func

logger = logging.getLogger(__name__)

from ..models.database import BenchmarkRun, Run, Step, db
from ..utils.errors import WebUIError, handle_errors

bp = Blueprint('analyze', __name__, url_prefix='/analyze')


class NoDataError(WebUIError):
    """No data available for analysis"""
    pass


@bp.route('/')
@handle_errors
def index():
    """Analysis page"""
    # Get recent runs for display
    recent_runs = Run.query.order_by(Run.start_time.desc()).limit(10).all()

    # Get available quest names
    quest_names = db.session.query(Run.quest_name).distinct().all()
    quest_names = [q[0] for q in quest_names]

    # Get agent types
    agent_types = db.session.query(Run.agent_id).distinct().all()
    agent_types = [a[0] for a in agent_types]

    # Get success rates
    stats = db.session.query(
        func.count(Run.id).label('total_runs'),
        func.sum(case((Run.outcome == 'SUCCESS', 1), else_=0)).label('successes')).first()

    success_rate = 0
    if stats and stats.total_runs > 0:
        success_rate = float(stats.successes / stats.total_runs) * 100

    # Get recent benchmarks
    recent_benchmarks = BenchmarkRun.query.order_by(BenchmarkRun.start_time.desc()).limit(5).all()

    return render_template('analyze/index.html',
                           recent_runs=recent_runs,
                           quest_names=quest_names,
                           agent_types=agent_types,
                           total_runs=stats.total_runs if stats else 0,
                           success_rate=success_rate,
                           recent_benchmarks=recent_benchmarks)


@bp.route('/summary')
@handle_errors
def summary():
    """Get summary statistics"""
    # Get overall statistics
    stats = db.session.query(
        func.count(Run.id).label('total_runs'),
        func.sum(case((Run.outcome == 'SUCCESS', 1), else_=0)).label('successes'),
        func.sum(case((Run.outcome == 'FAILURE', 1), else_=0)).label('failures')).first()

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
        func.sum(case(
            (Run.outcome == 'SUCCESS', 1),
            else_=0)).label('successes')).group_by(Run.quest_name,
                                                   func.json_extract(Run.agent_config,
                                                                     '$.model')).all()

    if not comparison:
        raise NoDataError("No comparison data available. Run some benchmarks first!")

    # Convert to list of dicts
    comparison_data = [{
        'quest_name': row[0],
        'model': row[1],
        'total_runs': row[2],
        'success_rate': float(row[3] / row[2]) if row[2] > 0 else 0
    } for row in comparison]

    return jsonify({'success': True, 'data': comparison_data})


@bp.route('/step_analysis')
@handle_errors
def step_analysis():
    """Analyze step-level metrics"""
    # Get step-level metrics
    steps = db.session.query(Run.quest_name, Step.location_id,
                             func.count(Step.id).label('visit_count')).join(
                                 Step,
                                 Run.id == Step.run_id).group_by(Run.quest_name,
                                                                 Step.location_id).all()

    if not steps:
        raise NoDataError("No step data available. Run some quests first!")

    # Convert to list of dicts
    step_data = [{
        'quest_name': row[0],
        'location_id': row[1],
        'visit_count': row[2]
    } for row in steps]

    return jsonify({'success': True, 'data': step_data})


@bp.route('/run/<int:run_id>')
@handle_errors
def run_details(run_id):
    """Show detailed analysis for a specific run"""
    run = Run.query.get_or_404(run_id)
    steps = Step.query.filter_by(run_id=run_id).order_by(Step.step).all()

    if not steps:
        raise NoDataError(f"No step data found for run {run_id}")

    # Calculate run metrics
    total_steps = len(steps)
    total_time = None
    if run.end_time and run.start_time:
        total_time = (run.end_time - run.start_time).total_seconds()

    # Count decision points (steps with multiple choices)
    decision_points = 0
    for step in steps:
        if step.choices and len(step.choices) > 1:
            decision_points += 1

    return render_template('analyze/run_details.html',
                           run=run,
                           steps=steps,
                           total_steps=total_steps,
                           total_time=total_time,
                           decision_points=decision_points)


@bp.route('/quest/<path:quest_name>')
@handle_errors
def quest_analysis(quest_name):
    """Analyze runs for a specific quest"""
    # Import datetime here to avoid potential circular imports
    from datetime import datetime

    # Get all runs for this quest
    runs = Run.query.filter_by(quest_name=quest_name).order_by(Run.start_time.desc()).all()

    if not runs:
        raise NoDataError(f"No runs found for quest: {quest_name}")

    # Calculate success rate
    total_runs = len(runs)
    success_runs = len([r for r in runs if r.outcome == 'SUCCESS'])
    success_rate = (success_runs / total_runs * 100) if total_runs > 0 else 0

    # Get agent performance
    agent_stats = {}
    for run in runs:
        agent_id = run.agent_id
        if agent_id not in agent_stats:
            agent_stats[agent_id] = {'total': 0, 'success': 0}

        agent_stats[agent_id]['total'] += 1
        if run.outcome == 'SUCCESS':
            agent_stats[agent_id]['success'] += 1

    # Calculate agent success rates
    for agent_id in agent_stats:
        stats = agent_stats[agent_id]
        stats['success_rate'] = (stats['success'] / stats['total'] *
                                 100) if stats['total'] > 0 else 0

    return render_template(
        'analyze/quest_analysis.html',
        quest_name=quest_name,
        runs=runs,
        total_runs=total_runs,
        success_rate=success_rate,
        agent_stats=agent_stats,
        now=datetime.utcnow(),  # Pass current time for the report
        datetime=datetime)  # Pass datetime module for template use


@bp.route('/run/<int:run_id>/analysis')
@handle_errors
def run_analysis(run_id):
    """Get detailed analysis for a specific run (API)"""
    run = Run.query.get_or_404(run_id)
    steps = Step.query.filter_by(run_id=run_id).order_by(Step.step).all()

    if not steps:
        raise NoDataError(f"No step data found for run {run_id}")

    # Calculate run metrics
    total_steps = len(steps)
    total_time = (run.end_time -
                  run.start_time).total_seconds() if run.end_time and run.start_time else None

    # Analyze step choices and responses
    step_metrics = []
    for step in steps:
        try:
            choices = step.choices and len(step.choices)
            step_metrics.append({
                'step': step.step,
                'location': step.location_id,
                'num_choices': choices,
                'action': step.action
            })
        except Exception as e:
            logger.warning(f"Error processing step {step.id}: {e}")
            continue

    analysis = {
        'success': True,
        'run_info': run.to_dict(),
        'metrics': {
            'total_steps': total_steps,
            'total_time': total_time,
            'decision_points': len([s for s in step_metrics if s.get('num_choices', 0) > 1])
        },
        'step_metrics': step_metrics
    }

    return jsonify(analysis)


@bp.route('/run/<int:run_id>/readable')
@handle_errors
def run_readable(run_id):
    """Get human-readable formatted view of a run"""
    run = Run.query.get_or_404(run_id)
    steps = Step.query.filter_by(run_id=run_id).order_by(Step.step).all()

    if not steps:
        raise NoDataError(f"No step data found for run {run_id}")

    # Extract quest name from quest_file if available, otherwise use quest_name
    quest_name = Path(run.quest_file).stem if run.quest_file else run.quest_name or "Unknown"

    # Format the run details in a human-readable way
    readable_output = []

    # Run header
    readable_output.append(f"QUEST: {quest_name}")

    # Get agent name from agent_config if available
    agent_name = run.agent_id if run.agent_id else "Unknown"
    if run.agent_config and isinstance(run.agent_config, dict) and 'model' in run.agent_config:
        agent_name = f"{agent_name} ({run.agent_config['model']})"

    readable_output.append(f"AGENT: {agent_name}")

    # Show number of steps instead of start time
    readable_output.append(f"STEPS: {len(steps)}")

    if run.end_time:
        readable_output.append(f"END TIME: {run.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    if run.outcome:
        readable_output.append(f"OUTCOME: {run.outcome}")
    readable_output.append("")
    readable_output.append("========== QUEST PLAYTHROUGH ==========")

    # Format each step
    for i, step in enumerate(steps):
        # Step header
        readable_output.append("")
        readable_output.append(f"----- STEP {step.step} -----")
        readable_output.append("")

        # Observation
        readable_output.append(f"{step.observation}")
        readable_output.append("")

        # Choices
        if step.choices and len(step.choices) > 0:
            readable_output.append("Available choices:")
            for i, choice in enumerate(step.choices):
                readable_output.append(f"{i+1}. {choice['text']}")
            readable_output.append("")

        # Action taken - only show for steps that have choices
        if step.action and step.choices and len(step.choices) > 0:
            choice_index = int(step.action) - 1
            if 0 <= choice_index < len(step.choices):
                choice_text = step.choices[choice_index]['text']
                readable_output.append(f"Selected option {step.action}: {choice_text}")
            readable_output.append("")

        # LLM reasoning and analysis if available
        if step.llm_response:
            try:
                # If llm_response is a string, try to parse it as JSON
                llm_response = step.llm_response

                # Handle both dictionary and object-like structures
                if llm_response:
                    # Try to get reasoning
                    reasoning = None
                    if isinstance(llm_response, dict) and 'reasoning' in llm_response:
                        reasoning = llm_response['reasoning']

                    if reasoning:
                        readable_output.append(f"Reasoning: {reasoning}")
                        readable_output.append("")

                    # Try to get analysis
                    analysis = None
                    if isinstance(llm_response, dict) and 'analysis' in llm_response:
                        analysis = llm_response['analysis']

                    if analysis:
                        readable_output.append(f"Analysis: {analysis}")
                        readable_output.append("")
            except Exception as e:
                logger.error(f"Error processing LLM response: {e}")
                logger.error(f"LLM response type: {type(step.llm_response)}")

    # Final outcome
    if run.outcome:
        readable_output.append("")
        readable_output.append(f"========== QUEST OUTCOME: {run.outcome} ==========")

    return jsonify({'success': True, 'readable_output': '\n'.join(readable_output)})


@bp.route('/benchmark/<int:benchmark_id>')
@handle_errors
def benchmark_analysis(benchmark_id):
    """Analyze benchmark results"""
    # Get benchmark run
    benchmark = BenchmarkRun.query.get_or_404(benchmark_id)

    # If completed, get results
    results = []
    if benchmark.status == 'complete' and benchmark.results:
        # Results are already stored as a Python object thanks to JSONEncodedDict
        # Add debug logging
        logger.info(f"Retrieved benchmark results from database: {type(benchmark.results)}")
        if isinstance(benchmark.results, list):
            logger.info(f"Results count: {len(benchmark.results)}")
            if benchmark.results:
                sample = benchmark.results[0]
                logger.info(
                    f"First result type: {type(sample)}, keys: {sample.keys() if hasattr(sample, 'keys') else 'N/A'}"
                )

        results = benchmark.results

    # For running benchmarks, try to gather partial results from runs with matching benchmark_id
    elif benchmark.status == 'running':
        runs = Run.query.filter_by(benchmark_id=benchmark.benchmark_id).all()
        for run in runs:
            results.append({
                'quest': run.quest_name,
                'model': run.agent_config.get('model') if run.agent_config else None,
                'temperature': run.agent_config.get('temperature') if run.agent_config else None,
                'template': run.agent_config.get('system_template') if run.agent_config else None,
                'agent_id': run.agent_id,
                'outcome': run.outcome,
                'reward': run.reward,
                'run_id': run.id
            })

    # Calculate summary statistics
    quest_names = list(set(r.get('quest', '') for r in results))
    models = list(set(r.get('model', '') for r in results if r.get('model')))
    total_runs = len(results)
    # Pre-calculate values for the template to reduce complexity in template rendering
    success_runs = len(
        [r for r in results if isinstance(r, dict) and r.get('outcome') == 'SUCCESS'])
    failure_runs = len(
        [r for r in results if isinstance(r, dict) and r.get('outcome') == 'FAILURE'])
    error_runs = len([
        r for r in results
        if isinstance(r, dict) and r.get('outcome') and r.get('outcome') not in ('SUCCESS',
                                                                                 'FAILURE')
    ])
    success_rate = (success_runs / total_runs * 100) if total_runs > 0 else 0

    # Get stats per model
    model_stats = {}
    for model in models:
        model_results = [r for r in results if r.get('model') == model]
        model_stats[model] = {
            'total':
                len(model_results),
            'success':
                len([r for r in model_results if r.get('outcome') == 'SUCCESS']),
            'failure':
                len([r for r in model_results if r.get('outcome') == 'FAILURE']),
            'error':
                len([
                    r for r in model_results
                    if r.get('outcome') and r.get('outcome') not in ('SUCCESS', 'FAILURE')
                ]),
        }

        # Calculate success rate
        if model_stats[model]['total'] > 0:
            model_stats[model]['success_rate'] = (model_stats[model]['success'] /
                                                  model_stats[model]['total']) * 100
        else:
            model_stats[model]['success_rate'] = 0

    return render_template('analyze/benchmark_analysis.html',
                           benchmark=benchmark,
                           results=results,
                           quest_names=quest_names,
                           models=models,
                           model_stats=model_stats,
                           total_runs=total_runs,
                           success_rate=success_rate,
                           success_runs=success_runs,
                           failure_runs=failure_runs,
                           error_runs=error_runs)


@bp.route('/export')
@handle_errors
def export_metrics():
    """Export metrics data in various formats"""
    # Parameters
    export_format = request.args.get('format', 'json')
    run_id = request.args.get('run_id')
    quest_name = request.args.get('quest_name')

    if run_id:
        # Export single run
        run = Run.query.get_or_404(int(run_id))
        steps = Step.query.filter_by(run_id=run.id).order_by(Step.step).all()

        # Format data
        run_data = run.to_dict()
        run_data['steps'] = [step.to_dict() for step in steps]

        return jsonify({'success': True, 'data': run_data})
    elif quest_name:
        # Export all runs for a quest
        runs = Run.query.filter_by(quest_name=quest_name).order_by(Run.start_time.desc()).all()

        if not runs:
            raise NoDataError(f"No runs found for quest: {quest_name}")

        # Format data
        results = {
            "quest_name": quest_name,
            "total_runs": len(runs),
            "outcomes": {
                "SUCCESS": 0,
                "FAILURE": 0
            },
            "runs": []
        }

        # Process each run
        for run in runs:
            results["outcomes"][run.outcome] = results["outcomes"].get(run.outcome, 0) + 1

            # Get steps for this run
            steps = Step.query.filter_by(run_id=run.id).order_by(Step.step).all()

            run_data = run.to_dict()
            run_data["steps"] = [step.to_dict() for step in steps]

            results["runs"].append(run_data)

        return jsonify({'success': True, 'data': results})
    else:
        # Export summary stats
        stats = db.session.query(
            func.count(Run.id).label('total_runs'),
            func.sum(case((Run.outcome == 'SUCCESS', 1), else_=0)).label('successes'),
            func.sum(case((Run.outcome == 'FAILURE', 1), else_=0)).label('failures')).first()

        if not stats or not stats.total_runs:
            raise NoDataError("No data available. Run some quests first!")

        summary = {
            'total_runs':
                stats.total_runs,
            'success_rate':
                float(stats.successes / stats.total_runs) if stats.total_runs > 0 else 0.0,
            'outcomes': {
                'SUCCESS': stats.successes or 0,
                'FAILURE': stats.failures or 0
            }
        }

        return jsonify({'success': True, 'data': summary})


@bp.errorhandler(NoDataError)
def handle_no_data_error(error):
    """Handle NoDataError by returning 400 status code"""
    return jsonify({'success': False, 'error': str(error)}), 400


@bp.route('/cleanup', methods=['POST'])
@handle_errors
def cleanup_data():
    """Clean up database records based on criteria

    Parameters:
    - older_than: ISO date string (YYYY-MM-DD) to delete records older than this date
    - run_ids: List of run IDs to delete
    - benchmark_ids: List of benchmark IDs to delete
    - all_runs: Boolean, if true delete all runs
    - all_benchmarks: Boolean, if true delete all benchmarks
    """
    data = request.get_json() or {}
    deleted_runs = 0
    deleted_benchmarks = 0

    try:
        # Delete runs older than a specific date
        if 'older_than' in data:
            try:
                cutoff_date = datetime.fromisoformat(data['older_than'])
                runs = Run.query.filter(Run.start_time < cutoff_date).all()
                run_ids = [run.id for run in runs]

                # Delete steps first (due to foreign key constraint)
                Step.query.filter(Step.run_id.in_(run_ids)).delete(synchronize_session=False)
                deleted_runs = Run.query.filter(Run.start_time < cutoff_date).delete(
                    synchronize_session=False)

                # Delete benchmark runs
                deleted_benchmarks = BenchmarkRun.query.filter(
                    BenchmarkRun.start_time < cutoff_date).delete(synchronize_session=False)
                db.session.commit()
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'Invalid date format. Use YYYY-MM-DD'
                }), 400

        # Delete specific run IDs
        if 'run_ids' in data and isinstance(data['run_ids'], list):
            for run_id in data['run_ids']:
                # Delete steps first
                Step.query.filter_by(run_id=run_id).delete()
                if Run.query.filter_by(id=run_id).delete():
                    deleted_runs += 1
            db.session.commit()

        # Delete specific benchmark IDs
        if 'benchmark_ids' in data and isinstance(data['benchmark_ids'], list):
            for benchmark_id in data['benchmark_ids']:
                if BenchmarkRun.query.filter_by(id=benchmark_id).delete():
                    deleted_benchmarks += 1
            db.session.commit()

        # Delete all runs if requested
        if data.get('all_runs', False):
            # Delete all steps first
            Step.query.delete()
            deleted_runs = Run.query.delete()
            db.session.commit()

        # Delete all benchmarks if requested
        if data.get('all_benchmarks', False):
            deleted_benchmarks = BenchmarkRun.query.delete()
            db.session.commit()

        return jsonify({
            'success':
                True,
            'deleted_runs':
                deleted_runs,
            'deleted_benchmarks':
                deleted_benchmarks,
            'message':
                f'Successfully deleted {deleted_runs} runs and {deleted_benchmarks} benchmarks'
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in cleanup_data: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.errorhandler(Exception)
def handle_error(error):
    """Handle other errors by returning 400 status code"""
    logger.error(f"Error in analyze view: {error}", exc_info=True)
    return jsonify({'success': False, 'error': str(error)}), 400
