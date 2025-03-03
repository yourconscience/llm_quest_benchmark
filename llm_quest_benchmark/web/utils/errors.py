"""Simple error handling utilities for web UI"""
from functools import wraps
from flask import jsonify
import logging

logger = logging.getLogger(__name__)

class WebUIError(Exception):
    """Base error for web UI"""
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code
        self.message = message

class QuestNotFoundError(WebUIError):
    """Quest file or directory not found"""
    pass

class InvalidModelError(WebUIError):
    """Invalid model specified"""
    pass

class InvalidChoiceError(WebUIError):
    """Invalid choice number"""
    pass

class RunNotFoundError(WebUIError):
    """Run not found"""
    pass

class RunCompletedError(WebUIError):
    """Run already completed"""
    pass

def handle_errors(f):
    """Simple error handling decorator for routes"""
    @wraps(f)
    def wrapped(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except WebUIError as e:
            logger.warning(f"Known error in {f.__name__}: {str(e)}")
            return jsonify({
                'success': False,
                'error': e.message
            }), e.status_code
        except Exception as e:
            logger.error(f"Unexpected error in {f.__name__}: {str(e)}", exc_info=True)
            return jsonify({
                'success': False,
                'error': "Something went wrong. Please try again or contact support."
            }), 500
    return wrapped

def validate_quest_file(quest_path):
    """Validate that quest path can be resolved to at least one quest file"""
    import logging
    from llm_quest_benchmark.core.quest_registry import validate_quest_path, get_registry
    
    logger = logging.getLogger(__name__)
    
    # Skip validation for glob patterns
    if '*' in quest_path:
        logger.info(f"Skipping validation for glob pattern: {quest_path}")
        return
    
    # Use the registry to validate the path
    if not validate_quest_path(quest_path):
        # Find similar paths for helpful error messages
        registry = get_registry()
        
        # If it looks like a directory path, try to suggest similar directories
        if '/' in quest_path and not quest_path.endswith('.qm'):
            basename = quest_path.split('/')[-1]
            similar = registry.search_quests(basename[:3])
            
            if similar:
                dirs = {info.directory for info in similar}
                if dirs:
                    suggestion = f". Did you mean: {', '.join(dirs)}?"
                    raise QuestNotFoundError(f"Quest directory not found: {quest_path}{suggestion}")
        
        # If it looks like a quest name, suggest similar quest names
        else:
            similar = registry.search_quests(quest_path[:3])
            if similar:
                names = {info.name for info in similar}
                if names:
                    suggestion = f". Did you mean: {', '.join(names)}?"
                    raise QuestNotFoundError(f"Quest not found: {quest_path}{suggestion}")
        
        raise QuestNotFoundError(f"Quest path not found: {quest_path}")

def validate_model(model):
    """Validate that model is supported"""
    from llm_quest_benchmark.constants import MODEL_CHOICES
    if model not in MODEL_CHOICES:
        raise InvalidModelError(f"Invalid model: {model}. Please choose from: {', '.join(MODEL_CHOICES)}")

def validate_choice(choice_num, choices):
    """Validate that choice number is valid"""
    from llm_quest_benchmark.utils.choice_mapper import ChoiceMapper

    logger.info(f"Validating choice: {choice_num}, choices: {choices}")

    try:
        choice_num = int(choice_num)
        logger.info(f"Converted choice to int: {choice_num}")
    except (ValueError, TypeError):
        logger.error(f"Invalid choice number (not an integer): {choice_num}")
        raise InvalidChoiceError(f"Invalid choice number: {choice_num}")

    try:
        choice_mapper = ChoiceMapper(choices)
        logger.info(f"Choice mapper keys: {list(choice_mapper.keys())}")

        if choice_num not in choice_mapper:
            logger.error(f"Choice {choice_num} not in valid choices: {list(choice_mapper.keys())}")
            raise InvalidChoiceError(f"Invalid choice: {choice_num}. Valid choices: {list(choice_mapper.keys())}")

        logger.info(f"Choice {choice_num} is valid")
        return choice_num
    except Exception as e:
        logger.error(f"Error in choice validation: {str(e)}")
        raise InvalidChoiceError(f"Error validating choice: {str(e)}")

def validate_run(run_id):
    """Validate that run exists and is not completed"""
    from ..models.database import Run

    run = Run.query.get(run_id)
    if not run:
        raise RunNotFoundError(f"Run not found: {run_id}")

    if run.end_time:
        raise RunCompletedError(f"Run {run_id} is already completed")

    return run