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
    """Quest file not found"""
    pass

class InvalidModelError(WebUIError):
    """Invalid model specified"""
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
    """Validate that quest file exists"""
    from pathlib import Path
    if not Path(quest_path).is_file():
        raise QuestNotFoundError(f"Quest file not found: {quest_path}")

def validate_model(model):
    """Validate that model is supported"""
    from llm_quest_benchmark.constants import MODEL_CHOICES
    if model not in MODEL_CHOICES:
        raise InvalidModelError(f"Invalid model: {model}. Please choose from: {', '.join(MODEL_CHOICES)}")