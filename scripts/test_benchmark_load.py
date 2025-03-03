#!/usr/bin/env python
"""Simple script to test loading benchmark results from database"""
import sys
from pathlib import Path
import json
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from flask import Flask
from llm_quest_benchmark.web.models.database import db, BenchmarkRun

def create_test_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{project_root}/instance/llm_quest.sqlite'
    db.init_app(app)
    return app

def test_load_benchmark():
    app = create_test_app()
    with app.app_context():
        # Get the most recent benchmark
        benchmark = BenchmarkRun.query.order_by(BenchmarkRun.start_time.desc()).first()
        if not benchmark:
            print("No benchmarks found")
            return
        
        print(f"Benchmark ID: {benchmark.id}")
        print(f"Name: {benchmark.name}")
        print(f"Status: {benchmark.status}")
        print(f"Start Time: {benchmark.start_time}")
        
        if benchmark.results:
            print(f"\nResults type: {type(benchmark.results)}")
            print(f"Results count: {len(benchmark.results) if isinstance(benchmark.results, list) else 'N/A'}")
            
            # Try to access first result
            if isinstance(benchmark.results, list) and benchmark.results:
                first_result = benchmark.results[0]
                print(f"\nFirst result type: {type(first_result)}")
                if hasattr(first_result, 'keys'):
                    print(f"Keys: {first_result.keys()}")
                    print(f"Sample values: quest={first_result.get('quest')}, outcome={first_result.get('outcome')}")
                else:
                    print(f"Result has no keys method: {first_result}")
        else:
            print("\nNo results available")
        
        print("\nBenchmark config:")
        if benchmark.config:
            print(f"Config type: {type(benchmark.config)}")
            if isinstance(benchmark.config, dict):
                for key, value in benchmark.config.items():
                    print(f"  {key}: {value}")
        else:
            print("No config available")

if __name__ == "__main__":
    test_load_benchmark()