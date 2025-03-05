#!/usr/bin/env python
"""Script to test the template rendering with benchmark data"""
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from flask import Flask, render_template

from llm_quest_benchmark.web.models.database import BenchmarkRun, db


def create_test_app():
    app = Flask(__name__, template_folder=str(project_root / 'llm_quest_benchmark/web/templates'))
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{project_root}/instance/llm_quest.sqlite'
    db.init_app(app)

    # Register Jinja filters used in the application
    @app.template_filter('tojson')
    def to_json(value):
        return json.dumps(value)

    return app


def test_render_template():
    app = create_test_app()
    with app.app_context():
        # Get the most recent benchmark
        benchmark = BenchmarkRun.query.order_by(BenchmarkRun.start_time.desc()).first()
        if not benchmark:
            logger.error("No benchmarks found")
            return

        # Prepare variables for template
        results = benchmark.results if benchmark.results else []

        # Calculate summary statistics similar to the analyze view
        quest_names = list(set(r.get('quest', '') for r in results))
        models = list(set(r.get('model', '') for r in results if r.get('model')))
        total_runs = len(results)

        # Pre-calculate values for the template - this is what we changed in our fix
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

        # Calculate model stats
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

        # Test rendering
        try:
            logger.info("Testing template rendering...")
            render_template('analyze/benchmark_analysis.html',
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

            logger.info("Template rendered successfully!")
            return True
        except Exception as e:
            logger.error(f"Error rendering template: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False


if __name__ == "__main__":
    test_render_template()
