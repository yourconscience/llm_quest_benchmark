#!/usr/bin/env python
"""Run the Flask app in debug mode"""
import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def main():
    from llm_quest_benchmark.web.app import create_app
    app = create_app()
    with app.app_context():
        try:
            import llm_quest_benchmark.web.views.analyze
            logging.getLogger('llm_quest_benchmark.web.views.analyze').setLevel(logging.DEBUG)
        except Exception as e:
            logger.error(f"Error importing analyze views: {e}")
    
    print("\nRunning Flask app in debug mode")
    print("Available routes:")
    for rule in app.url_map.iter_rules():
        print(f"  {rule}")
    
    print("\nHOW TO USE:")
    print("  1. Start the server: llm-quest server")
    print("  2. Run a benchmark through the web interface")
    print("  3. Access the benchmark results through the Analyze link")
    print("\nThe database is stored at:")
    print(f"  {project_root}/instance/llm_quest.sqlite\n")

if __name__ == "__main__":
    main()
