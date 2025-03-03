"""Text processing utilities for Space Rangers quests"""
import re
import logging
from typing import Any, Dict, List, Tuple, Optional

from llm_quest_benchmark.constants import CREDIT_REWARD_PATTERN, SUCCESS_INDICATORS, FAILURE_INDICATORS

logger = logging.getLogger(__name__)


def clean_qm_text(text: str) -> str:
    """Remove QM-specific tags and normalize text"""
    if not text:
        return ""
        
    # Remove color tags
    text = re.sub(r'<clr>|<clrEnd>', '', text)
    # Normalize newlines
    text = text.replace('\r\n', '\n')
    # Remove redundant newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def process_game_state(raw_state: Dict[str, Any]) -> Dict[str, Any]:
    """Process game state dictionary, cleaning all text fields"""
    return {
        'text':
            clean_qm_text(raw_state['text']),
        'paramsState':
            raw_state['paramsState'],
        'choices': [{
            **choice, 'text': clean_qm_text(choice['text'])
        } for choice in raw_state['choices']]
    }


def detect_quest_outcome(text: str) -> Tuple[bool, float, str]:
    """Detect quest outcome from text based on various indicators
    
    This centralized utility analyzes quest text to determine success or failure
    using multiple detection methods including:
    - Credit reward detection (e.g., "10000 cr")
    - Success phrase identification
    - Failure phrase identification
    
    Args:
        text: Quest text to analyze
        
    Returns:
        Tuple of (success: bool, reward: float, reason: str)
    """
    if not text:
        return False, 0.0, "no_text"
    
    # Check for credit rewards in text (e.g., "10000 cr")
    credit_matches = CREDIT_REWARD_PATTERN.findall(text)
    
    # Convert to integers and check if any are positive
    if credit_matches:
        credit_values = [int(val) for val in credit_matches if val.isdigit()]
        if any(val > 0 for val in credit_values):
            logger.debug(f"Quest success detected from credit reward: {credit_values}")
            return True, float(max(credit_values)), "credit_reward"
    
    # Check for success indicators in lower case text
    text_lower = text.lower()
    
    # Check for success indicators
    for indicator in SUCCESS_INDICATORS:
        if indicator in text_lower:
            logger.debug(f"Quest success detected from indicator: {indicator}")
            return True, 1.0, "success_indicator"
    
    # Check for failure indicators
    for indicator in FAILURE_INDICATORS:
        if indicator in text_lower:
            logger.debug(f"Quest failure detected from indicator: {indicator}")
            return False, 0.0, "failure_indicator"
    
    # Default: no clear indicators found
    return False, 0.0, "no_indicators"


def wrap_text(text: str, width: int = 150) -> str:
    """Wrap text to specified width for better readability
    
    Wraps text to the specified width while preserving existing paragraph breaks.
    Useful for improving readability in UI displays.
    
    Args:
        text: Text to wrap
        width: Maximum width before wrapping
        
    Returns:
        Wrapped text
    """
    if not text:
        return ""
    
    # Split text into paragraphs (preserve existing line breaks)
    paragraphs = text.split('\n')
    wrapped_paragraphs = []
    
    for paragraph in paragraphs:
        if not paragraph.strip():
            wrapped_paragraphs.append("")
            continue
            
        # Initialize variables for line wrapping
        words = paragraph.split()
        current_line = []
        current_length = 0
        
        # Process each word
        for word in words:
            # If adding this word would exceed width
            if current_length + len(word) + (1 if current_length > 0 else 0) > width:
                # Add current line to wrapped paragraphs
                wrapped_paragraphs.append(" ".join(current_line))
                # Start a new line with the current word
                current_line = [word]
                current_length = len(word)
            else:
                # Add word to current line
                current_line.append(word)
                # Update length (add 1 for space if not first word)
                current_length += len(word) + (1 if current_length > 0 else 0)
        
        # Add the last line if there's anything left
        if current_line:
            wrapped_paragraphs.append(" ".join(current_line))
    
    # Join paragraphs with line breaks
    return "\n".join(wrapped_paragraphs)
