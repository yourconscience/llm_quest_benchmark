#!/usr/bin/env python
"""Debug script to check template parsing without running a server"""
import json
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def debug_template():
    """Check if a template has syntax errors by parsing it directly"""
    from jinja2 import Environment, FileSystemLoader

    # Set up Jinja environment similar to Flask
    template_path = project_root / "llm_quest_benchmark/web/templates"
    env = Environment(loader=FileSystemLoader(template_path))

    # Add custom filters similar to Flask template filters
    env.filters['tojson'] = lambda x: json.dumps(x)

    try:
        # Try to load and parse the template
        template = env.get_template("analyze/benchmark_analysis.html")
        logger.info("Template parsed successfully without syntax errors")
        return True
    except Exception as e:
        logger.error(f"Error parsing template: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    debug_template()
